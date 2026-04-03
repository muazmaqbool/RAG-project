import os
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
DB_PASSWORD = os.getenv("DB_PASSWORD")

client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=FIREWORKS_API_KEY,
)

app = FastAPI(title="E-Commerce RAG API")

# 1. Update the Request Model to accept hard filters
class SearchQuery(BaseModel):
    query: str
    top_k: int = 5
    min_price: int | None = None  # Optional filter
    max_price: int | None = None  # Optional filter

def get_db_connection():
    return psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password=DB_PASSWORD,
        host="localhost",
        port="5432"
    )

def generate_query_vector(text):
    try:
        response = client.embeddings.create(
            model="nomic-ai/nomic-embed-text-v1.5",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate search vector.")

@app.post("/search")
def semantic_search(request: SearchQuery):
    query_vector = generate_query_vector(request.query)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 2. Dynamically build the SQL query based on provided filters
    sql = """
        SELECT title, url, price_pkr, description, 
               1 - (embedding <=> %s::vector) AS similarity_score
        FROM products
        WHERE 1=1 
    """
    
    # The parameters list will safely inject our variables to prevent SQL injection
    sql_params = [query_vector]
    
    # Apply hard SQL filters BEFORE the vector sorting
    if request.min_price is not None:
        sql += " AND price_pkr >= %s"
        sql_params.append(request.min_price)
        
    if request.max_price is not None:
        sql += " AND price_pkr <= %s"
        sql_params.append(request.max_price)
        
    # Add the final sorting and limit logic
    sql += """
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """
    sql_params.extend([query_vector, request.top_k])
    
    try:
        cursor.execute(sql, tuple(sql_params))
        results = cursor.fetchall()
        
        formatted_results = []
        for row in results:
            formatted_results.append({
                "title": row[0],
                "url": row[1],
                "price": row[2],
                "description": row[3],
                "match_score": round(row[4] * 100, 2)
            })
            
        return {"query": request.query, "results": formatted_results}
        
    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database search failed.")
    finally:
        cursor.close()
        conn.close()

@app.post("/recommend")
def get_ai_recommendation(request: SearchQuery):
    """
    The full RAG endpoint: Retrieves the top 5 laptops, then uses Mixtral 
    to synthesize a final recommendation for the user.
    """
    # 1. Get the top 5 raw database matches
    search_results = semantic_search(request)["results"]
    
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
    
    Here are the top {len(search_results)} products we have in our database that match their search:
    {context_string}
    
    Based ONLY on these provided products, write a short, friendly recommendation. 
    Explicitly pick ONE product as the "Top Recommendation" and explain why it fits their specific search query. 
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
            "recommendation": recommendation_text,
            "products": search_results
        }
    except Exception as e:
        print(f"LLM Synthesis error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate AI recommendation.")
    
@app.get("/")
def read_root():
    return {"status": "API is running. Use POST /search to query."}