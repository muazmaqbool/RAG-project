import os
import json
import asyncio
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI  # <--- UPGRADED
from dotenv import load_dotenv

load_dotenv()

# --- UPGRADED: Using AsyncOpenAI natively ---
client = AsyncOpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=os.getenv("FIREWORKS_API_KEY"),
)

# Load Master Schema
SCHEMA_PATH = 'data/processed/master_schema.json'
if os.path.exists(SCHEMA_PATH):
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        MASTER_SCHEMAS = json.load(f)
else:
    MASTER_SCHEMAS = {"General": {}}

app = FastAPI(title="Agentic E-Commerce RAG")

class SearchQuery(BaseModel):
    query: str
    top_k: int = 5
    min_price: int | None = None  
    max_price: int | None = None  

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port="5432"
    )

# --- CORE UTILITIES ---
def extract_json_from_text(raw_text):
    try:
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            return json.loads(raw_text[start_idx:end_idx + 1])
    except Exception as e:
        print(f"JSON Parsing Error: {e}")
    return {}

# --- NEW: NATIVE ASYNC RETRY WRAPPER ---
async def safe_api_call(coro_func, max_retries=4):
    """Wraps an async API call with exponential backoff to defeat 429 Rate Limits."""
    for attempt in range(max_retries):
        try:
            return await coro_func()
        except Exception as e:
            print(f"⚠️ API Error (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return None
            await asyncio.sleep(2 ** attempt) # Waits 1s, 2s, 4s to naturally stagger bursts

async def generate_vector(text):
    async def call():
        return await client.embeddings.create(model="nomic-ai/nomic-embed-text-v1.5", input=text)
    res = await safe_api_call(call)
    return res.data[0].embedding if res else None

# --- STAGE 1: THE PLANNER ---
async def plan_search_intents(user_query: str):
    prompt = f"""
    Break the user query into distinct product searches.
    CATEGORIES: {list(MASTER_SCHEMAS.keys())}
    
    Return JSON: {{ "items": [ {{ "sub_query": "...", "category": "..." }} ] }}
    Query: "{user_query}"
    """
    async def call():
        return await client.chat.completions.create(
            model="accounts/fireworks/models/mixtral-8x22b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
    
    response = await safe_api_call(call)
    if not response: return []
    
    content = response.choices[0].message.content
    parsed = extract_json_from_text(content)
    return parsed.get("items", [])

# --- STAGE 2: THE EXECUTOR ---
async def execute_sub_query(item, request_params, limit):
    sub_query = item['sub_query']
    category = item['category']
    vector = await generate_vector(sub_query)
    
    if not vector:
        print(f"❌ Failed to generate vector for {sub_query}")
        return []
        
    category_schema = MASTER_SCHEMAS.get(category, MASTER_SCHEMAS["General"])
    
    filter_prompt = f"""
    User Query: "{sub_query}"
    Category: "{category}"
    Schema Rules: {json.dumps(category_schema, indent=2)}

    CRITICAL INSTRUCTIONS:
    1. Identify only the specific technical requirements mentioned in the query.
    2. Map them to the EXACT keys in the Schema Rules. 
    3. THE VALUE MUST BE THE RAW DATA (Integer, Float, Boolean, or Short String).
    4. FATAL ERROR: Do NOT copy the description text from the schema. 
       - Bad: "processor_name": "String. Extract the full CPU name..."
       - Good: "graphics_memory_gb": 4
    5. Return an empty object {{}} if no technical specs are explicitly mentioned.

    Return EXACTLY a JSON object.
    """
    async def call():
        return await client.chat.completions.create(
            model="accounts/fireworks/models/mixtral-8x22b-instruct",
            messages=[{"role": "user", "content": filter_prompt}],
            temperature=0.0
        )
        
    filter_res = await safe_api_call(call)
    spec_filters = extract_json_from_text(filter_res.choices[0].message.content) if filter_res else {}
    print(f"🔍 DEBUG: Generated Filters for {category}: {spec_filters}")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        sql = """
            SELECT title, url, price_pkr, description, search_specs, display_specs,
                   1 - (embedding <=> %s::vector) AS score
            FROM products
            WHERE is_available = True
        """
        params = [vector]
        sql += " AND categories::text ILIKE %s"; params.append(f"%{category}%")

        if request_params.min_price:
            sql += " AND price_pkr >= %s"; params.append(request_params.min_price)
        if request_params.max_price:
            sql += " AND price_pkr <= %s"; params.append(request_params.max_price)

        # Apply Strict JSONB filters
        spec_conditions = []
        for key, value in spec_filters.items():
            spec_conditions.append("search_specs @> %s::jsonb") # <--- Added ::jsonb cast
            params.append(json.dumps({key: value}))
        
        final_sql = sql + (" AND " + " AND ".join(spec_conditions) if spec_conditions else "")
        final_sql += " ORDER BY score DESC LIMIT %s"
        
        cursor.execute(final_sql, params + [limit])
        rows = cursor.fetchall()

        # SOFT FALLBACK: Strip spec filters but keep vector + category + price
        is_fallback = False  # <--- NEW: Track if fallback triggers
        
        if not rows and spec_conditions:
            is_fallback = True  # <--- NEW: Flag it
            print(f"⚠️ Soft-filter: No exact match for {spec_filters}. Retrying with vector only.")
            base_params = params[:len(params)-len(spec_conditions)]
            cursor.execute(sql + " ORDER BY score DESC LIMIT %s", base_params + [limit])
            rows = cursor.fetchall()

        # PROTECTED MAPPING
        results = []
        for row in rows:
            results.append({
                "title": row.get('title', 'N/A'),
                "url": row.get('url', '#'),
                "price": row.get('price_pkr', 0),
                "description": row.get('description', ''),
                "display_specs": row.get('display_specs', {}),
                "match_score": round(row.get('score', 0) * 100, 2),
                "matched_intent": category,
                "is_exact_match": bool(spec_conditions) and not is_fallback # <--- NEW: Flag exact matches
            })
        return results

    finally:
        cursor.close()
        conn.close()

# --- API ENDPOINTS ---
@app.post("/search")
async def semantic_search(request: SearchQuery):
    intents = await plan_search_intents(request.query)
    if not intents: intents = [{"sub_query": request.query, "category": "General"}]
    
    # 1. Fetch results for each intent
    tasks = [execute_sub_query(intent, request, request.top_k) for intent in intents]
    all_results = await asyncio.gather(*tasks) # This is a List of Lists
    
    # 2. Sort each sub-list individually (Exact Matches first, then Vector Score)
    for sublist in all_results:
        sublist.sort(key=lambda x: (x.get('is_exact_match', False), x['match_score']), reverse=True)
    
    # 3. The "Round-Robin" Zipper Merge
    final_results = []
    max_len = max((len(sublist) for sublist in all_results), default=0)
    
    for i in range(max_len):
        for sublist in all_results:
            if i < len(sublist):
                final_results.append(sublist[i])
                
            # Stop the moment we hit the user's requested limit
            if len(final_results) >= request.top_k:
                break
        if len(final_results) >= request.top_k:
            break
            
    return {"query": request.query, "results": final_results}

@app.post("/recommend")
async def get_ai_recommendation(request: SearchQuery):
    search_data = await semantic_search(request)
    results = search_data["results"]
    if not results: return {"explanation": "No products found matching those criteria.", "top_picks": [], "alternatives": []}

    context = ""
    for i, r in enumerate(results):
        context += f"[{i+1}] Title: {r['title']} | URL: {r['url']} | Price: {r['price']} | Specs: {json.dumps(r['display_specs'])}\n"

    prompt = f"""
    User Query: "{request.query}"
    Products:
    {context}
    Pick the absolute best match(es) for the user's intent. Explain why using the specs. 
    Return JSON: {{ "explanation": "...", "top_picks": [ {{ "url": "exact_url_from_context", "reason": "..." }} ] }}
    """
    
    async def call():
        return await client.chat.completions.create(
            model="accounts/fireworks/models/mixtral-8x22b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
    response = await safe_api_call(call)
    
    if not response:
        # Fallback if API fails completely: Return results without AI reasoning
        return {"explanation": "Server load is high, but here are the best database matches:", "top_picks": [results[0]], "alternatives": results[1:]}
        
    content = response.choices[0].message.content
    parsed = extract_json_from_text(content)
    
    top_urls = [p.get("url") for p in parsed.get("top_picks", [])]
    top_picks_list = []
    alternatives_list = []
    
    for r in results:
        if r['url'] in top_urls:
            r['ai_selected'] = True
            top_picks_list.append(r)
        else:
            r['ai_selected'] = False
            alternatives_list.append(r)
            
    if not top_picks_list and results:
        results[0]['ai_selected'] = True
        top_picks_list.append(results[0])
        alternatives_list = results[1:]

    return {
        "explanation": parsed.get("explanation", "Here are the best recommendations we found."),
        "top_picks": top_picks_list,
        "alternatives": alternatives_list
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)