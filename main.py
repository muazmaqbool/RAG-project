import os
import json
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Initialize the OpenAI client pointing to Fireworks AI
client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=FIREWORKS_API_KEY,
)

# Initialize FastAPI app
app = FastAPI(title="E-Commerce RAG API")

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

# --- TAXONOMY LOADER ---
TAXONOMY_FILE = 'data/raw/category_taxonomy.json'
VALID_CATEGORIES = []

if os.path.exists(TAXONOMY_FILE):
    with open(TAXONOMY_FILE, 'r', encoding='utf-8') as f:
        taxonomy_tree = json.load(f)
        
    # Recursive function to pull just the names out of your nested JSON tree
    def extract_category_names(nodes):
        names = []
        for node in nodes:
            names.append(node['name'])
            if 'subcategories' in node:
                names.extend(extract_category_names(node['subcategories']))
        return names
        
    VALID_CATEGORIES = list(set(extract_category_names(taxonomy_tree)))
    print(f"Loaded {len(VALID_CATEGORIES)} official categories from taxonomy.")
else:
    print("WARNING: category_taxonomy.json not found. Routing will be less accurate.")

def extract_json_from_text(raw_text):
    """
    Strips away conversational filler and markdown backticks from an LLM response,
    isolating just the JSON object.
    """
    try:
        # Find the index of the first opening brace
        start_idx = raw_text.find('{')
        # Find the index of the last closing brace
        end_idx = raw_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            # Slice the string to only include the JSON part
            clean_json_string = raw_text[start_idx:end_idx + 1]
            return json.loads(clean_json_string)
        else:
            raise ValueError("No JSON structure found in the text.")
            
    except json.JSONDecodeError as e:
        print(f"Failed to parse cleaned JSON: {e}")
        return None

# --- CORE AI FUNCTIONS ---
def extract_search_intent(user_query: str):
    """
    The Query Decomposer: Uses Schema-Grounded Extraction to map user intents 
    strictly to our existing database taxonomy.
    """
    prompt = f"""
    You are an e-commerce search planner. Analyze this user query: "{user_query}"
    
    You MUST map the user's requests strictly to our database's official categories.
    
    OFFICIAL CATEGORIES:
    {VALID_CATEGORIES}
    
    1. Break the query down into distinct product requests.
    2. For each request, write a clean "sub_query".
    3. Choose the closest matching "primary_category" ONLY from the OFFICIAL CATEGORIES list. Do not invent or guess categories. If nothing matches, use null.
    
    Return EXACTLY a JSON object with this structure:
    {{
      "items": [
        {{
          "sub_query": "gaming laptop",
          "primary_category": "Laptops"
        }},
        {{
          "sub_query": "gaming headphones",
          "primary_category": "Headphones"
        }}
      ]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            # Change this line right here!
            model="accounts/fireworks/models/mixtral-8x22b-instruct", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, 
        )
        
        # Grab the raw, messy text from the LLM
        raw_output = response.choices[0].message.content.strip()
        print(f"--- RAW LLM OUTPUT ---\n{raw_output}\n----------------------")
        
        # Clean it using our new function
        parsed_response = extract_json_from_text(raw_output)
        
        if parsed_response:
            return parsed_response.get("items", [])
        else:
            return []
            
    except Exception as e:
        print(f"Decomposition error: {e}")
        return []
            
    except Exception as e:
        print(f"Decomposition error: {e}")
        return []

def generate_query_vector(text):
    """Turns the user's search text into a 768-dimension vector."""
    try:
        response = client.embeddings.create(
            model="nomic-ai/nomic-embed-text-v1.5",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate search vector.")
    
# --- API ENDPOINTS ---
@app.post("/search")
def semantic_search(request: SearchQuery):
    print("\n" + "="*50)
    print(f"🔍 1. RAW USER QUERY: {request.query}")
    
    # 1. Decompose the query
    items_list = extract_search_intent(request.query)
    
    print(f"🧠 2. LLM DECOMPOSITION OUTPUT:")
    print(json.dumps(items_list, indent=2))
    
    # Fallback if decomposition fails
    if not items_list:
        print("🚨 WARNING: LLM returned empty list! Triggering fallback to full string.")
        items_list = [{"sub_query": request.query, "primary_category": None}]
        
    print(f"🚀 3. FINAL LIST GOING TO DATABASE LOOP:")
    print(json.dumps(items_list, indent=2))
    print("="*50 + "\n")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    final_results = []
    
    # Calculate how many to fetch per intent to build a diverse cart
    limit_per_item = max(2, request.top_k // max(1, len(items_list)))
    print(f"📊 4. LIMIT PER ITEM: Fetching {limit_per_item} products per sub-query.")
    
    try:
        # 2. Execute a dedicated search for EACH decomposed item
        for i, item in enumerate(items_list):
            print(f"  -> Executing Sub-Query {i+1}: '{item['sub_query']}' (Category: {item.get('primary_category')})")
            
            # Generate a clean math vector for THIS specific item only
            clean_vector = generate_query_vector(item["sub_query"])
            
            sql = """
                SELECT title, url, price_pkr, description, 
                       1 - (embedding <=> %s::vector) AS similarity_score
                FROM products
                WHERE 1=1 
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
            sql_params.extend([clean_vector, limit_per_item])
            
            cursor.execute(sql, tuple(sql_params))
            results = cursor.fetchall()
            print(f"     ✅ Found {len(results)} matches for Sub-Query {i+1}")
            
            for row in results:
                final_results.append({
                    "title": row[0],
                    "url": row[1],
                    "price": row[2],
                    "description": row[3],
                    "match_score": round(row[4] * 100, 2),
                    "matched_intent": item.get("primary_category", "General") 
                })

        return {"query": request.query, "intents_used": items_list, "results": final_results}
        
    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database search failed.")
    finally:
        cursor.close()
        conn.close()

@app.post("/recommend")
def get_ai_recommendation(request: SearchQuery):
    # 1. Get the raw database matches and intents
    search_data = semantic_search(request)
    search_results = search_data["results"]
    intents_used = search_data["intents_used"]
    
    if not search_results:
        return {"explanation": "I couldn't find any products matching those criteria.", "top_picks": [], "alternatives": []}
        
    # 2. Extract intent names to tell the LLM exactly what to pick
    intent_names = [intent.get("primary_category", "General") for intent in intents_used if intent.get("primary_category")]
    if not intent_names:
        intent_names = ["Requested Items"]
        
    # 3. Format the context for the LLM
    context_string = ""
    for i, p in enumerate(search_results):
        context_string += f"\n[{i+1}] Title: {p['title']}\nCategory: {p['matched_intent']}\nURL: {p['url']}\nPrice: {p['price']} PKR\nDescription: {p['description']}\n"
        
    # 4. Prompt Mixtral for MULTIPLE picks
    prompt = f"""
    You are an expert e-commerce hardware assistant. 
    A user just searched for: "{request.query}"
    
    We identified they are looking for these categories: {intent_names}
    
    Here are the top products we have in our database:
    {context_string}
    
    For EACH category identified above, pick ONE product as the absolute "Top Recommendation". 
    Write a short explanation of why you chose this specific combination of items for the user.
    
    You MUST return EXACTLY a JSON object with two keys:
    1. "explanation": Your conversational advice explaining the choices (1-2 paragraphs).
    2. "top_picks": A JSON list of objects, where each object contains the "category" and the exact "url" of the single best product for that category.
    """
    
    try:
        response = client.chat.completions.create(
            model="accounts/fireworks/models/mixtral-8x22b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, 
            response_format={"type": "json_object"} 
        )
        parsed_response = json.loads(response.choices[0].message.content.strip())
        
        explanation = parsed_response.get("explanation", "Here are our top recommendations.")
        top_picks_metadata = parsed_response.get("top_picks", [])
        
        # Extract just the URLs of the winners
        top_pick_urls = [pick.get("url") for pick in top_picks_metadata]
        
        # 5. Split the payload into Winners and Alternatives
        top_picks_list = []
        alternatives_list = []
        
        for p in search_results:
            if p["url"] in top_pick_urls:
                p["ai_selected"] = True
                top_picks_list.append(p)
            else:
                alternatives_list.append(p)
                
        # Safety net: If the LLM glitches and returns no URLs, default to the top math result
        if not top_picks_list and search_results:
            top_picks_list.append(search_results[0])
            alternatives_list = search_results[1:]
        
        return {
            "query": request.query,
            "intents_used": intents_used,
            "explanation": explanation,
            "top_picks": top_picks_list,
            "alternatives": alternatives_list
        }
    except Exception as e:
        print(f"LLM Synthesis error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate AI recommendation.")

@app.get("/")
def read_root():
    return {"status": "API is running. Use POST /search or POST /recommend to query."}