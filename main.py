import os
import json
import psycopg2
import re
import operator
import difflib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
DB_PASSWORD = os.getenv("DB_PASSWORD")

client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=FIREWORKS_API_KEY,
)

app = FastAPI(title="E-Commerce Agentic RAG API")

# --- REQUEST SCHEMAS ---
class SearchQuery(BaseModel):
    query: str
    top_k: int = 5
    min_price: int | None = None  
    max_price: int | None = None  

# --- DATABASE CONNECTION ---
def get_db_connection():
    return psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password=DB_PASSWORD,
        host="localhost",
        port="5432"
    )

# --- TAXONOMY & SCHEMA LOADERS ---
def load_json_list(filepath, default_msg):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            if "category_taxonomy" in filepath.lower():
                data = json.load(f)
                def extract_names(nodes):
                    names = []
                    for node in nodes:
                        names.append(node['name'])
                        if 'subcategories' in node:
                            names.extend(extract_names(node['subcategories']))
                    return names
                return list(set(extract_names(data)))
    print(default_msg)
    return []

def load_specs_schema(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    print(f"WARNING: {filepath} not found.")
    return {"master_list": [], "categories": {}}

VALID_CATEGORIES = load_json_list('data/raw/category_taxonomy.json', "WARNING: category_taxonomy.json not found.")
SPECS_SCHEMA = load_specs_schema('category_specifications.json')

# --- CORE UTILITIES ---
def extract_json_from_text(raw_text):
    try:
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            return json.loads(raw_text[start_idx:end_idx + 1])
        return None
    except Exception:
        return None

def generate_query_vector(text):
    try:
        response = client.embeddings.create(
            model="nomic-ai/nomic-embed-text-v1.5",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate search vector.")

# --- POST-FILTERING MATH ENGINE ---
OPS = { "==": operator.eq, ">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt }

def evaluate_constraints(product_specs, title, description, constraints):
    if not constraints:
        return True 

    # Pre-extract all numbers from the title and description for our Stage 2 fallback
    full_text = f"{title} {description}".lower()
    text_numbers = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", full_text)]

    for constraint in constraints:
        trait = constraint.get("trait", "").lower()
        req_val = constraint.get("value")
        op_str = constraint.get("operator", "==")
        op_func = OPS.get(op_str, operator.eq)

        # Ensure the LLM gave us a valid number to check against
        try:
            req_val = float(req_val)
        except Exception:
            continue 

        spec_matched = False
        actual_spec_str = None

        # --- STAGE 1: Strict JSON Specifications Check ---
        if isinstance(product_specs, dict):
            # 1a. Exact/Substring Match
            for k, v in product_specs.items():
                if trait in k.lower() or k.lower() in trait:
                    actual_spec_str = str(v)
                    break
            
            # 1b. Fuzzy Matching
            if not actual_spec_str:
                spec_keys = list(product_specs.keys())
                fuzzy_matches = difflib.get_close_matches(trait, spec_keys, n=1, cutoff=0.5)
                if fuzzy_matches:
                    actual_spec_str = str(product_specs[fuzzy_matches[0]])

            if actual_spec_str:
                matches = re.findall(r"[-+]?\d*\.\d+|\d+", actual_spec_str)
                if matches:
                    try:
                        actual_val = float(matches[0])
                        if op_func(actual_val, req_val):
                            spec_matched = True
                    except Exception:
                        pass

        # --- STAGE 2: The Raw Text Fallback ---
        text_matched = False
        if not spec_matched:
            # Check if ANY number extracted from the title/description satisfies the constraint
            for num in text_numbers:
                if op_func(num, req_val):
                    text_matched = True
                    # Optional: Print statement to watch the fallback in action
                    # print(f"📝 Text Fallback: Passed constraint '{op_str} {req_val}' using the number '{num}' found in text.")
                    break

        # If BOTH the JSON check AND the Text fallback fail, the product fails this constraint
        if not spec_matched and not text_matched:
            return False

    return True

# --- AGENT 1: THE PLANNER ---
def extract_search_intent(user_query: str):
    """Breaks down the query into distinct items and assigns a core category."""
    prompt = f"""
    You are an e-commerce search planner. Break the query down into distinct product requests.
    
    OFFICIAL CATEGORIES: {VALID_CATEGORIES}
    
    For each distinct item the user wants:
    1. Write a clean "sub_query" describing the item and its requirements.
    2. Pick the closest "primary_category" ONLY from the OFFICIAL CATEGORIES list.
    
    Return EXACTLY a JSON object:
    {{
      "items": [
        {{
          "sub_query": "powerbank with 65watt charging",
          "primary_category": "Power Banks"
        }}
      ]
    }}
    
    User Query: "{user_query}"
    """
    try:
        response = client.chat.completions.create(
            model="accounts/fireworks/models/mixtral-8x22b-instruct", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        parsed = extract_json_from_text(response.choices[0].message.content.strip())
        return parsed.get("items", []) if parsed else []
    except Exception as e:
        print(f"Planner error: {e}")
        return [] 

# --- AGENT 2: THE EXECUTOR ---
def extract_item_constraints(sub_query: str, valid_keys: list):
    """Extracts numerical specs using ONLY the strictly provided keys for that category."""
    if not valid_keys:
        return []

    prompt = f"""
    You are a strict technical specification extractor.
    
    User Request: "{sub_query}"
    ALLOWED SPECIFICATION KEYS: {valid_keys}
    
    Extract numerical constraints (max 5) from the request.
    FATAL RULES:
    1. For "trait", you MUST copy the exact string from the ALLOWED SPECIFICATION KEYS list. Do not invent keys.
    2. "operator" MUST be one of: ["==", ">=", "<=", ">", "<"]
    3. "value" MUST be a pure number.
    
    Return EXACTLY a JSON object:
    {{
      "constraints": [
        {{"trait": "Power Output", "operator": ">=", "value": 65}}
      ]
    }}
    """
    try:
        response = client.chat.completions.create(
            model="accounts/fireworks/models/mixtral-8x22b-instruct", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        parsed = extract_json_from_text(response.choices[0].message.content.strip())
        
        # Python Kill-Switch for Hallucinations during Inference
        constraints = parsed.get("constraints", []) if parsed else []
        valid_constraints = [c for c in constraints if c.get("trait") in valid_keys]
        
        if len(valid_constraints) < len(constraints):
            print("🛡️ Inference Filter: Blocked a hallucinated constraint key.")
            
        return valid_constraints
    except Exception as e:
        print(f"Executor error: {e}")
        return []

# --- API ENDPOINTS ---
@app.post("/search")
def semantic_search(request: SearchQuery):
    # 1. Run The Planner
    items_list = extract_search_intent(request.query)
    
    if not items_list:
        items_list = [{"sub_query": request.query, "primary_category": "General", "constraints": []}]
    
    # 2. Run The Executor for each planned item
    for item in items_list:
        category = item.get("primary_category", "")
        
        # Look up the specific keys for this category. Fallback to master list if not found.
        category_map = SPECS_SCHEMA.get("categories", {})
        
        # Try to find an exact or partial match in our category schema
        valid_keys = []
        for schema_cat, keys in category_map.items():
            if category.lower() in schema_cat.lower():
                valid_keys.extend(keys)
                
        valid_keys = list(set(valid_keys))
        if not valid_keys:
            valid_keys = SPECS_SCHEMA.get("master_list", [])
            
        print(f"🧠 Executor routing '{category}' to {len(valid_keys)} specific keys.")
        
        # Fetch constraints using the specific keys
        item["constraints"] = extract_item_constraints(item["sub_query"], valid_keys)
        
    print(f"🎯 Final Structured Intent: {json.dumps(items_list, indent=2)}")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    final_results = []
    
    limit_per_item = max(2, request.top_k // max(1, len(items_list)))
    sql_overfetch_limit = 50
    
    try:
        for item in items_list:
            clean_vector = generate_query_vector(item["sub_query"])
            
            sql = """
                SELECT title, url, price_pkr, description, 
                       1 - (embedding <=> %s::vector) AS similarity_score,
                       specifications
                FROM products
                WHERE is_available = True 
            """
            sql_params = [clean_vector]
            
            if request.min_price is not None:
                sql += " AND price_pkr >= %s"
                sql_params.append(request.min_price)
            if request.max_price is not None:
                sql += " AND price_pkr <= %s"
                sql_params.append(request.max_price)
                
            if item.get("primary_category") and item.get("primary_category") != "General":
                sql += " AND categories::text ILIKE %s"
                sql_params.append(f"%{item['primary_category']}%")
                
            sql += " ORDER BY embedding <=> %s::vector LIMIT %s;"
            sql_params.extend([clean_vector, sql_overfetch_limit])
            
            cursor.execute(sql, tuple(sql_params))
            raw_db_results = cursor.fetchall()
            
            passed_items = []
            failed_items = []
            
            for row in raw_db_results:
                product_data = {
                    "title": row[0], "url": row[1], "price": row[2], 
                    "description": row[3], "match_score": round(row[4] * 100, 2),
                    "specifications": row[5], "matched_intent": item.get("primary_category", "General")
                }
                
                if evaluate_constraints(row[5], row[0], row[3], item.get("constraints", [])):
                    passed_items.append(product_data)
                else:
                    failed_items.append(product_data)
            
            constraints_met = True
            if passed_items:
                winners = passed_items[:limit_per_item]
            else:
                constraints_met = False
                winners = failed_items[:limit_per_item] if failed_items else []
                
            for w in winners:
                w["constraints_met"] = constraints_met
                final_results.append(w)

        return {"query": request.query, "intents_used": items_list, "results": final_results}
        
    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database search failed.")
    finally:
        cursor.close()
        conn.close()

# ... (Keep your /recommend endpoint the exact same as before!)

@app.post("/recommend")
def get_ai_recommendation(request: SearchQuery):
    search_data = semantic_search(request)
    search_results = search_data["results"]
    intents_used = search_data["intents_used"]
    
    if not search_results:
        return {"explanation": "I couldn't find any products in stock matching those criteria.", "top_picks": [], "alternatives": []}
        
    context_string = ""
    for i, p in enumerate(search_results):
        # We explicitly tell Mixtral if this product failed the strict math check!
        flag = "[PERFECT MATCH]" if p.get("constraints_met", True) else "[PARTIAL MATCH - FAILED SPEC CHECK]"
        context_string += f"\n[{i+1}] {flag} Title: {p['title']}\nCategory: {p['matched_intent']}\nURL: {p['url']}\nPrice: {p['price']} PKR\nDescription: {p['description']}\n"
        
    prompt = f"""
    You are an expert e-commerce hardware assistant. A user searched for: "{request.query}"
    
    Here are the top products from our database:
    {context_string}
    
    For EACH category requested, pick ONE product as the absolute "Top Recommendation". 
    If a product is marked [PARTIAL MATCH], it means we didn't have the exact specifications they asked for. You MUST politely explain that you are offering the closest available alternative.
    
    Return EXACTLY a JSON object with two keys:
    1. "explanation": Your conversational advice explaining the choices.
    2. "top_picks": A JSON list containing the "category" and "url" of your winners.
    """
    
    try:
        response = client.chat.completions.create(
            model="accounts/fireworks/models/mixtral-8x22b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        parsed = extract_json_from_text(response.choices[0].message.content.strip())
        
        top_pick_urls = [pick.get("url") for pick in parsed.get("top_picks", [])] if parsed else []
        
        top_picks_list = []
        alternatives_list = []
        
        for p in search_results:
            if p["url"] in top_pick_urls:
                p["ai_selected"] = True
                top_picks_list.append(p)
            else:
                alternatives_list.append(p)
                
        if not top_picks_list and search_results:
            top_picks_list.append(search_results[0])
            alternatives_list = search_results[1:]
        
        return {
            "query": request.query,
            "intents_used": intents_used,
            "explanation": parsed.get("explanation", "Here are your recommendations.") if parsed else "Here are your matches.",
            "top_picks": top_picks_list,
            "alternatives": alternatives_list
        }
    except Exception as e:
        print(f"LLM Synthesis error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate AI recommendation.")