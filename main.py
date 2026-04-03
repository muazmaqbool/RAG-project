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

# --- CORE AI FUNCTIONS ---
def extract_search_intent(user_query: str):
    """
    The Query Planner: Breaks a complex user prompt into a list of distinct search intents.
    Uses the fast Llama 3.1 8B model for millisecond routing.
    """
    prompt = f"""
    You are an e-commerce search planner. Analyze this user query: "{user_query}"
    
    Break the query down into distinct product intents. 
    For example, if the user asks for "a new laptop and a powerbank", that is TWO intents.
    If the user asks for "new or used laptops", treat "New Laptops" and "Used Laptops" as TWO separate intents if they are standard retail categories.
    
    Rules for each intent:
    1. "primary_category": The main item (e.g., Laptops, Monitors, Powerbanks). Elevate accessories to primary.
    2. "minor_category": The brand or subtype (e.g., Dell, Gaming). Can be null.
    
    Return EXACTLY a JSON object with a single key "intents", which contains a LIST of intent objects.
    Example output format:
    {{
      "intents": [
        {{"primary_category": "Laptops", "minor_category": "Gaming"}},
        {{"primary_category": "Powerbanks", "minor_category": null}}
      ]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="accounts/fireworks/models/llama-v3p1-8b-instruct", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, 
            response_format={"type": "json_object"}
        )
        parsed_response = json.loads(response.choices[0].message.content.strip())
        return parsed_response.get("intents", [])
    except Exception as e:
        print(f"Intent extraction error: {e}")
        return [] # Return empty list on failure so vector search can fall back to general semantic search

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
    """
    1. Plans the query (extracts intents).
    2. Embeds the user query.
    3. Performs sub-queries for each intent using Hybrid Search (SQL + Vector).
    4. Combines and returns the top matches.
    """
    # 1. Query Planning
    intents_list = extract_search_intent(request.query)
    print(f"Extracted Intents: {intents_list}")
    
    # Fallback: If the LLM failed or found no specific intent, do one general search
    if not intents_list:
        intents_list = [{"primary_category": None, "minor_category": None}]
        
    # 2. Embed the text
    query_vector = generate_query_vector(request.query)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    all_formatted_results = []
    
    # Determine how many items to fetch PER category to keep the total around top_k
    # Ensure we always fetch at least 2 items per intent to give them choices
    limit_per_intent = max(2, request.top_k // len(intents_list))
    
    try:
        # 3. Execute a sub-query for EACH intent
        for intent in intents_list:
            sql = """
                SELECT title, url, price_pkr, description, 
                       1 - (embedding <=> %s::vector) AS similarity_score
                FROM products
                WHERE 1=1 
            """
            sql_params = [query_vector]
            
            # Apply hard SQL filters
            if request.min_price is not None:
                sql += " AND price_pkr >= %s"
                sql_params.append(request.min_price)
            if request.max_price is not None:
                sql += " AND price_pkr <= %s"
                sql_params.append(request.max_price)
                
            # Inject the specific intent filters for this iteration
            if intent.get("primary_category"):
                sql += " AND categories::text ILIKE %s"
                sql_params.append(f"%{intent['primary_category']}%")
                
            if intent.get("minor_category"):
                sql += " AND (categories::text ILIKE %s OR title ILIKE %s)"
                sql_params.extend([f"%{intent['minor_category']}%", f"%{intent['minor_category']}%"])
                
            # Add ordering and limits
            sql += " ORDER BY embedding <=> %s::vector LIMIT %s;"
            sql_params.extend([query_vector, limit_per_intent])
            
            cursor.execute(sql, tuple(sql_params))
            results = cursor.fetchall()
            
            for row in results:
                all_formatted_results.append({
                    "title": row[0],
                    "url": row[1],
                    "price": row[2],
                    "description": row[3],
                    "match_score": round(row[4] * 100, 2),
                    "matched_intent": intent.get("primary_category", "General") # Tag it for the UI
                })
                
        # Optional: Sort the final combined list by match_score to ensure the best stuff is at the top
        all_formatted_results = sorted(all_formatted_results, key=lambda x: x["match_score"], reverse=True)
        
        # Ensure we don't accidentally return 15 items if they asked for 5 intents
        final_results = all_formatted_results[:max(request.top_k, len(all_formatted_results))]

        return {"query": request.query, "intents_used": intents_list, "results": final_results}
        
    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database search failed.")
    finally:
        cursor.close()
        conn.close()

@app.post("/recommend")
def get_ai_recommendation(request: SearchQuery):
    """
    The full RAG endpoint: Retrieves the top database results, then uses Mixtral 
    to synthesize a final, personalized recommendation for the user.
    """
    # 1. Get the raw database matches
    search_data = semantic_search(request)
    search_results = search_data["results"]
    intents_used = search_data["intents_used"]
    
    if not search_results:
        return {"recommendation": "I couldn't find any products matching those criteria.", "products": []}
        
    # 2. Format the context for the LLM
    context_string = ""
    for i, p in enumerate(search_results):
        context_string += f"\n[{i+1}] {p['title']} - Price: {p['price']} PKR\nDescription: {p['description']}\n"
        
    # 3. Prompt Mixtral to act as the Sales Assistant
    prompt = f"""
    You are an expert e-commerce hardware assistant. 
    A user just searched for: "{request.query}"
    
    Here are the top products we have in our database that match their search:
    {context_string}
    
    Based ONLY on these provided products, write a short, friendly recommendation. 
    Explicitly pick ONE product as the "Top Recommendation" and explain why it fits their specific search query. 
    If the user asked for multiple types of items (like a laptop AND a mouse), ensure you recommend a complete setup from the provided products.
    Keep it concise (1-2 short paragraphs).
    """
    
    try:
        response = client.chat.completions.create(
            model="accounts/fireworks/models/mixtral-8x22b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, 
            max_tokens=300
        )
        recommendation_text = response.choices[0].message.content.strip()
        
        return {
            "query": request.query,
            "intents_used": intents_used,
            "recommendation": recommendation_text,
            "products": search_results
        }
    except Exception as e:
        print(f"LLM Synthesis error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate AI recommendation.")

@app.get("/")
def read_root():
    return {"status": "API is running. Use POST /search or POST /recommend to query."}