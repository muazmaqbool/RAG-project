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
    Break the user query into distinct product searches and extract any budget constraints.
    
    CRITICAL RULES:
    1. Group ALL features for a single product into ONE SINGLE sub_query.
    2. Extract budget limits if mentioned (e.g., "under 50k", "between 20000 and 50000"). Convert "k" to thousands (e.g., 50k = 50000).
    3. If no budget is mentioned, return null for min_price and max_price.
    4. If bluetooth or wireless is not mentioned with handsfree, it belongs in the stereo handsfree section.
    5. The base category for bluetooth related items is bluetooth handsfree. Bluetooth or wireless earbuds and bluetooth or wireless handsfree/neckband belong to the bluetooth handsfree category.
    6. IMPORTANT: ALL headphones go into the speakers and headphones category. They DO NOT belong to the bluetooth handsfree category. Headphones and earuds are different items.
    
    CATEGORIES: {list(MASTER_SCHEMAS.keys())}
    
    Return EXACTLY a JSON object in this format: 
    {{ 
      "min_price": 20000, 
      "max_price": 50000, 
      "items": [ {{ "sub_query": "...", "category": "..." }} ] 
    }}
    
    Query: "{user_query}"
    """
    async def call():
        return await client.chat.completions.create(
            model="accounts/fireworks/models/llama-v3p3-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
    
    response = await safe_api_call(call)
    if not response: return {"min_price": None, "max_price": None, "items": []}
    
    content = response.choices[0].message.content
    return extract_json_from_text(content)

# --- STAGE 2: THE EXECUTOR ---
async def execute_sub_query(item, request_params, limit):
    sub_query = item['sub_query']
    category = item['category']
    vector = await generate_vector(sub_query)
    
    if not vector:
        print(f"❌ Failed to generate vector for {sub_query}")
        return []
        
    category_schema = MASTER_SCHEMAS.get(category, MASTER_SCHEMAS["General"])
    
    # 1. CLEAN SCHEMA (Keys + Types only) to prevent instruction leaking
    clean_schema = {k: v.split('.')[0] for k, v in category_schema.items()}

    # We pass the FULL schema with your descriptions so the LLM knows exactly what the keys mean.
    filter_prompt = f"""
    User Query: "{sub_query}"
    Category: "{category}"
    SCHEMA REFERENCE DICTIONARY: {json.dumps(category_schema, indent=2)}

    CRITICAL INSTRUCTIONS:
    1. Extract ONLY specific technical requirements explicitly mentioned in the user query.
    2. Map them to the EXACT keys in the SCHEMA REFERENCE DICTIONARY.
    3. OMIT UNMENTIONED KEYS: If a requirement isn't explicitly clear, completely leave that key out. 
    4. FATAL ERROR (DO NOT COPY SCHEMA TEXT): NEVER use schema instructions (e.g., "String. MUST be one of...") as the output value.
    5. FATAL ERROR (NO SUBJECTIVE TERMS): Words like "latest", "best", "fast", or "new" are NOT technical specs. OMIT them entirely.
    6. VALUE FORMATTING & OPERATORS (CRITICAL):
       - Exact match: "brand": "HP"
       - Numbers (range): {{"ram_gb": {{"operator": ">=", "value": 16}}}}
       - Partial Strings (Fuzzy Match): If the user mentions a fragment like "i7" or "Ryzen", you MUST use ilike: {{"processor_name": {{"operator": "ilike", "value": "i7"}}}}
       - Multiple Options (OR logic): If the user asks for Intel OR AMD, use in: {{"processor_brand": {{"operator": "in", "value": ["Intel", "AMD"]}}}}
       - Allowed operators: ">=", "<=", ">", "<", "=", "ilike", "in"
       - STRICT RULE: ONLY use math (>, <) for numbers. NEVER use math operators for strings!
    
    EXAMPLES:
    - Query: "at least 16gb ram" -> {{"ram_gb": {{"operator": ">=", "value": 16}}}}
    - Query: "an i7 laptop with max 8gb vram" -> {{"processor_name": {{"operator": "ilike", "value": "i7"}}, "graphics_memory_gb": {{"operator": "<=", "value": 8}}}}
    - Query: "Intel or AMD processor" -> {{"processor_brand": {{"operator": "in", "value": ["Intel", "AMD"]}}}}

    Return EXACTLY a JSON object.
    """
    async def call():
        return await client.chat.completions.create(
            model="accounts/fireworks/models/llama-v3p3-70b-instruct",
            messages=[{"role": "user", "content": filter_prompt}],
            temperature=0.0
        )
        
    filter_res = await safe_api_call(call)
    raw_filters = extract_json_from_text(filter_res.choices[0].message.content) if filter_res else {}
    
    # 🧹 THE FIX: Strip out any empty strings, None/nulls, or zero-length lists
    spec_filters = {k: v for k, v in raw_filters.items() if v not in ("", None, [], {})}
    
    print(f"🔍 DEBUG: Cleaned Filters for {category}: {spec_filters}")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        sql = """
            SELECT title, url, price_pkr, description, search_specs, display_specs, image_url,
                   1 - (embedding <=> %s::vector) AS score
            FROM products
            WHERE is_available = True
        """
        params = [vector]
        # OPTIMIZED: Target the dedicated TEXT column instead of parsing the JSONB array
        sql += " AND leaf_category ILIKE %s"; params.append(f"%{category}%")

        if request_params.min_price:
            sql += " AND price_pkr >= %s"; params.append(request_params.min_price)
        if request_params.max_price:
            sql += " AND price_pkr <= %s"; params.append(request_params.max_price)

        # Take a safe snapshot of the base parameters BEFORE adding strict specs
        base_params = list(params)
        # Apply Strict JSONB filters with Advanced Operator Support
        spec_conditions = []
        allowed_operators = {">=", "<=", ">", "<", "=", "in", "ilike"} # <-- NEW: Added in & ilike
        
        for key, value in spec_filters.items():
            if isinstance(value, dict) and "operator" in value and "value" in value:
                op = value["operator"].lower()
                val = value["value"]
                
                if op in allowed_operators:
                    if op in {">=", "<=", ">", "<"}:
                        # MATH: Safely cast to numeric for greater/less than
                        spec_conditions.append(f"(search_specs->>%s)::numeric {op} %s")
                        params.extend([key, val])
                    
                    elif op == "=":
                        # EXACT TEXT: Safely compare as text to avoid numeric crashes
                        spec_conditions.append(f"(search_specs->>%s) = %s::text")
                        params.extend([key, str(val)])
                        
                    elif op == "ilike":
                        # FUZZY TEXT: "i7" will match "Core i7 12700H"
                        spec_conditions.append(f"(search_specs->>%s) ILIKE %s")
                        params.extend([key, f"%{val}%"])
                        
                    elif op == "in" and isinstance(val, list):
                        # MULTIPLE CHOICE: Matches if the value is ANY of the items in the list
                        spec_conditions.append(f"(search_specs->>%s) = ANY(%s::text[])")
                        params.extend([key, val])
            else:
                # Standard exact match
                spec_conditions.append("search_specs @> %s::jsonb")
                params.append(json.dumps({key: value}))
        
        final_sql = sql + (" AND " + " AND ".join(spec_conditions) if spec_conditions else "")
        final_sql += " ORDER BY score DESC LIMIT %s"
        
        # --- THE GRACEFUL FALLBACK FIX ---
        try:
            cursor.execute(final_sql, params + [limit])
            rows = cursor.fetchall()
        except psycopg2.Error as db_err:
            print(f"⚠️ SQL Math/Casting Error: {db_err}")
            conn.rollback() # VERY IMPORTANT: Resets the aborted Postgres transaction
            rows = [] # Force the script to use the vector fallback below

        # SOFT FALLBACK: Strip spec filters but keep vector + category + price
        is_fallback = False  # <--- NEW: Track if fallback triggers
        
        if not rows and spec_conditions:
            is_fallback = True  # <--- NEW: Flag it
            print(f"⚠️ Soft-filter failed or crashed. Retrying with vector only.")
            cursor.execute(sql + " ORDER BY score DESC LIMIT %s", base_params + [limit])
            rows = cursor.fetchall()

        # PROTECTED MAPPING
        results = []
        for row in rows:
            raw_display = row.get('display_specs', {})
            backup_display = row.get('search_specs', {})
            final_display = raw_display if raw_display else backup_display

            results.append({
                "title": row.get('title', 'N/A'),
                "url": row.get('url', '#'),
                "image_url": row.get('image_url'), 
                "price": row.get('price_pkr', 0),
                "description": row.get('description', ''),
                "display_specs": final_display, 
                "search_specs": row.get('search_specs', {}),
                "match_score": round(row.get('score', 0) * 100, 2),
                "matched_intent": category,
                "is_exact_match": bool(spec_conditions) and not is_fallback
            })

        # --- THE CONFIDENCE THRESHOLD (SEMANTIC THINNING) ---
        # If we have exact spec matches, drop the ones with poor semantic relevance.
        # This organically reduces the output to 1 or 2 items if only a few are truly relevant.
        if results and spec_conditions and not is_fallback:
            top_score = results[0]['match_score']
            # Keep items that are within 12% of the absolute best vector score
            results = [r for r in results if r['match_score'] >= (top_score - 12.0)]
            
        return results

    finally:
        cursor.close()
        conn.close()
# --- API ENDPOINTS ---
@app.post("/search")
async def semantic_search(request: SearchQuery):
    planner_data = await plan_search_intents(request.query)
    
    # Fallback if the planner failed
    if not planner_data or not planner_data.get("items"): 
        intents = [{"sub_query": request.query, "category": "General"}]
        ai_min, ai_max = None, None
    else:
        intents = planner_data["items"]
        ai_min = planner_data.get("min_price")
        ai_max = planner_data.get("max_price")
    
    # AI budget from text overrides the UI sidebar budget!
    effective_min = ai_min if ai_min is not None else request.min_price
    effective_max = ai_max if ai_max is not None else request.max_price
    
    # Temporarily update the request object so execute_sub_query uses the right prices
    request.min_price = effective_min
    request.max_price = effective_max

    # --- DYNAMIC LIMIT DETERMINATION ---
    num_intents = len(intents)
    if num_intents == 1:
        limit_per_intent = 5
    elif num_intents == 2:
        limit_per_intent = 4
    elif num_intents == 3:
        limit_per_intent = 2
    else:
        limit_per_intent = 1
    
    # 1. Fetch results for each intent
    tasks = [execute_sub_query(intent, request, limit_per_intent) for intent in intents]
    all_results = await asyncio.gather(*tasks) 
    
    # 2. Sort each sub-list individually (Exact Matches first, then Vector Score)
    for sublist in all_results:
        if not sublist: 
            continue
        sublist.sort(key=lambda x: (x.get('is_exact_match', False), x['match_score']), reverse=True)
    
    # 3. The "Round-Robin" Zipper Merge
    final_results = []
    max_len = max((len(sublist) for sublist in all_results), default=0)
    
    for i in range(max_len):
        for sublist in all_results:
            if i < len(sublist):
                final_results.append(sublist[i])
            
    return {"query": request.query, "results": final_results}

@app.post("/recommend")
async def get_ai_recommendation(request: SearchQuery):
    search_data = await semantic_search(request)
    results = search_data["results"]
    if not results: return {"explanation": "No products found matching those criteria.", "top_picks": [], "alternatives": []}

    # --- DYNAMIC AI PROMPT RULES ---
    unique_intents = list(set(r['matched_intent'] for r in results))
    num_intents = len(unique_intents)
    
    ai_rules = f"""
    CRITICAL RULES FOR TOP PICKS:
    1. The user is asking for items across {num_intents} categories: {', '.join(unique_intents)}.
    2. You MUST pick a MAXIMUM of 2 absolute best matches per category for the 'top_picks' list.
    3. FATAL ERROR: Do NOT exceed 2 top picks for any single category. Leave additional matches out of 'top_picks' (they will automatically be shown to the user as 'alternatives').
    """

    # We MUST include the category in the context string so Mixtral can count them!
    context = ""
    for i, r in enumerate(results):
        context += f"[{i+1}] Category: {r['matched_intent']} | Title: {r['title']} | URL: {r['url']} | Price: {r['price']} | Specs: {json.dumps(r['display_specs'])}\n"

    prompt = f"""
    User Query: "{request.query}"
    Products:
    {context}
    
    {ai_rules}
    
    CRITICAL TONE INSTRUCTIONS FOR 'explanation':
    1. Act as a friendly, expert tech store assistant.
    2. Address the user DIRECTLY (use "you" and "your"). 
    3. NEVER use third-person or robotic phrasing.
    4. Speak naturally. Say things like, "Here are some great options for your setup..."
    5. Seamlessly weave the technical specs into your conversational advice.
    6. FATAL ERROR: DO NOT start your explanation with a list of products, bullet points, or headers like "Recommendations:". Start IMMEDIATELY with your friendly greeting.
    7. JSON SYNTAX (CRITICAL): Do NOT use raw double quotes (") inside your explanation text. If you need to mention screen sizes, use the word 'inches' or a single quote (e.g., 15.6'). Unescaped double quotes will fatally break the system!
    
    Return EXACTLY a JSON object: {{ "explanation": "...", "top_picks": [ {{ "url": "exact_url_from_context", "reason": "..." }} ] }}
    """
    
    async def call():
        return await client.chat.completions.create(
            model="accounts/fireworks/models/mixtral-8x22b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1 # Lowered temperature slightly to make it strictly follow the counting rules
        )
        
    response = await safe_api_call(call)
    
    if not response:
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