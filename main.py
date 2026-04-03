import os
import json
import psycopg2
import re
import operator
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
            # Flatten taxonomy tree if it's the category file
            if "category" in filepath.lower():
                data = json.load(f)
                def extract_names(nodes):
                    names = []
                    for node in nodes:
                        names.append(node['name'])
                        if 'subcategories' in node:
                            names.extend(extract_names(node['subcategories']))
                    return names
                return list(set(extract_names(data)))
            else:
                return json.load(f)
    print(default_msg)
    return []

VALID_CATEGORIES = load_json_list('data/raw/category_taxonomy.json', "WARNING: category_taxonomy.json not found.")
VALID_SPECS = load_json_list('data/processed/unique_specifications.json', "WARNING: unique_specifications.json not found.")

# --- CORE UTILITIES ---
def extract_json_from_text(raw_text):
    """Slices away conversational filler/markdown to isolate the JSON object."""
    try:
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            return json.loads(raw_text[start_idx:end_idx + 1])
        raise ValueError("No JSON structure found.")
    except Exception as e:
        print(f"JSON Extraction Failed: {e}")
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

def evaluate_constraints(product_specs, constraints):
    """Evaluates numerical LLM constraints against raw product spec strings using Regex."""
    if not constraints:
        return True 

    for constraint in constraints:
        trait = constraint.get("trait", "").lower()
        req_val = constraint.get("value")
        op_str = constraint.get("operator", "==")
        op_func = OPS.get(op_str, operator.eq)

        # 1. Find matching key in the product's actual specs (case-insensitive)
        actual_spec_str = None
        if isinstance(product_specs, dict):
            for k, v in product_specs.items():
                if trait in k.lower():
                    actual_spec_str = str(v)
                    break

        if not actual_spec_str:
            return False # Product doesn't even have this specification listed

        # 2. Extract the first valid number from the product's string (e.g., "16 GB" -> 16.0)
        matches = re.findall(r"[-+]?\d*\.\d+|\d+", actual_spec_str)
        if not matches:
            return False 

        try:
            actual_val = float(matches[0])
            req_val = float(req_val)
            if not op_func(actual_val, req_val):
                return False
        except Exception:
            return False

    return True

# --- THE ROUTER ---
def extract_search_intent(user_query: str):
    prompt = f"""
    You are an e-commerce search planner. Break the query down into distinct product requests.
    
    OFFICIAL CATEGORIES: {VALID_CATEGORIES}
    VALID SPECIFICATION KEYS: {VALID_SPECS}
    
    For each distinct item the user wants:
    1. Write a clean "sub_query".
    2. Pick the closest "primary_category" ONLY from the OFFICIAL CATEGORIES.
    3. Extract numerical constraints (max 5 per item) using ONLY the VALID SPECIFICATION KEYS for the "trait".
       - "operator" MUST be one of: ["==", ">=", "<=", ">", "<"]
       - "value" MUST be a pure number.
    
    Return EXACTLY a JSON object:
    {{
      "items": [
        {{
          "sub_query": "gaming laptop 16gb ram",
          "primary_category": "Laptops",
          "constraints": [
            {{"trait": "Ram", "operator": ">=", "value": 16, "unit": "GB"}}
          ]
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
        raw_output = response.choices[0].message.content.strip()
        parsed = extract_json_from_text(raw_output)
        return parsed.get("items", []) if parsed else []
    except Exception as e:
        print(f"Router error: {e}")
        return [] 

# --- API ENDPOINTS ---
@app.post("/search")
def semantic_search(request: SearchQuery):
    items_list = extract_search_intent(request.query)
    print(f"🧠 Decomposed Intent: {json.dumps(items_list, indent=2)}")
    
    if not items_list:
        items_list = [{"sub_query": request.query, "primary_category": None, "constraints": []}]
        
    conn = get_db_connection()
    cursor = conn.cursor()
    final_results = []
    
    # We want a diverse cart, but we OVER-FETCH in SQL so we have items to filter
    limit_per_item = max(2, request.top_k // max(1, len(items_list)))
    sql_overfetch_limit = 20 
    
    try:
        for item in items_list:
            clean_vector = generate_query_vector(item["sub_query"])
            
            # PRE-FILTERING: Notice `is_available = True` and we pull the `specifications` column
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
                
            if item.get("primary_category"):
                sql += " AND categories::text ILIKE %s"
                sql_params.append(f"%{item['primary_category']}%")
                
            sql += " ORDER BY embedding <=> %s::vector LIMIT %s;"
            sql_params.extend([clean_vector, sql_overfetch_limit])
            
            cursor.execute(sql, tuple(sql_params))
            raw_db_results = cursor.fetchall()
            
            # POST-FILTERING
            passed_items = []
            failed_items = []
            
            for row in raw_db_results:
                product_data = {
                    "title": row[0], "url": row[1], "price": row[2], 
                    "description": row[3], "match_score": round(row[4] * 100, 2),
                    "specifications": row[5], "matched_intent": item.get("primary_category", "General")
                }
                
                # Run it through the regex math engine
                if evaluate_constraints(row[5], item.get("constraints", [])):
                    passed_items.append(product_data)
                else:
                    failed_items.append(product_data)
            
            # THE GRACEFUL DEGRADATION LOGIC
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