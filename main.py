import os
import json
import asyncio
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
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
    """Safely extracts JSON even if the LLM wraps it in markdown code blocks."""
    try:
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            return json.loads(raw_text[start_idx:end_idx + 1])
    except Exception as e:
        print(f"JSON Parsing Error: {e}")
    return {}

async def generate_vector(text):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: client.embeddings.create(
        model="nomic-ai/nomic-embed-text-v1.5",
        input=text
    ))
    return response.data[0].embedding

# --- STAGE 1: THE PLANNER ---
async def plan_search_intents(user_query: str):
    prompt = f"""
    Break the user query into distinct product searches.
    CATEGORIES: {list(MASTER_SCHEMAS.keys())}
    
    Return JSON: {{ "items": [ {{ "sub_query": "...", "category": "..." }} ] }}
    Query: "{user_query}"
    """
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: client.chat.completions.create(
        model="accounts/fireworks/models/mixtral-8x22b-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    ))
    
    content = response.choices[0].message.content
    parsed = extract_json_from_text(content)
    return parsed.get("items", [])

# --- STAGE 2: THE EXECUTOR ---
async def execute_sub_query(item, request_params, limit):
    sub_query = item['sub_query']
    category = item['category']
    vector = await generate_vector(sub_query)
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
    loop = asyncio.get_event_loop()
    filter_res = await loop.run_in_executor(None, lambda: client.chat.completions.create(
        model="accounts/fireworks/models/mixtral-8x22b-instruct",
        messages=[{"role": "user", "content": filter_prompt}],
        temperature=0.0
    ))
    
    content = filter_res.choices[0].message.content
    spec_filters = extract_json_from_text(content)
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
            spec_conditions.append("search_specs @> %s")
            params.append(json.dumps({key: value}))
        
        final_sql = sql + (" AND " + " AND ".join(spec_conditions) if spec_conditions else "")
        final_sql += " ORDER BY score DESC LIMIT %s"
        
        cursor.execute(final_sql, params + [limit])
        rows = cursor.fetchall()

        # SOFT FALLBACK: Strip spec filters but keep vector + category + price
        if not rows and spec_conditions:
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
                "matched_intent": category
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
    
    # Let each intent fetch the FULL top_k amount to ensure a rich candidate pool
    tasks = [execute_sub_query(intent, request, request.top_k) for intent in intents]
    all_results = await asyncio.gather(*tasks)
    
    flattened = [item for sublist in all_results for item in sublist]
    
    # Sort the combined pool by match_score and slice the absolute best top_k
    flattened.sort(key=lambda x: x['match_score'], reverse=True)
    return {"query": request.query, "results": flattened[:request.top_k]}

@app.post("/recommend")
async def get_ai_recommendation(request: SearchQuery):
    search_data = await semantic_search(request)
    results = search_data["results"]
    if not results: return {"explanation": "No products found matching those criteria.", "top_picks": [], "alternatives": []}

    context = ""
    for i, r in enumerate(results):
        # We MUST include the URL here so the LLM knows what to return
        context += f"[{i+1}] Title: {r['title']} | URL: {r['url']} | Price: {r['price']} | Specs: {json.dumps(r['display_specs'])}\n"

    prompt = f"""
    User Query: "{request.query}"
    Products:
    {context}
    Pick the absolute best match(es) for the user's intent. Explain why using the specs. 
    Return JSON: {{ "explanation": "...", "top_picks": [ {{ "url": "exact_url_from_context", "reason": "..." }} ] }}
    """
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: client.chat.completions.create(
        model="accounts/fireworks/models/mixtral-8x22b-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    ))
    
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
            
    # Safety net: if LLM fails to match URLs properly, default to highest score
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