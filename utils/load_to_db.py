import json
import os
import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector
from psycopg2.extras import execute_values  # Added for high-speed bulk insert
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Postgres connection parameters
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

# This should point to your NEW dual-layer dataset
INPUT_FILE = 'data/processed/dual_layer_dataset.json'

def get_db_connection():
    """Connects to Postgres and enables vector math support."""
    conn = psycopg2.connect(**DB_PARAMS)
    register_vector(conn)
    return conn

def load_data_to_db():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Could not find {INPUT_FILE}. Run normalize_dataset.py first!")
        return

    print(f"📖 Loading {INPUT_FILE}...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    conn = get_db_connection()
    cursor = conn.cursor()

    # UPDATED QUERY: Uses search_specs and display_specs instead of 'specifications'
    # Uses EXCLUDED syntax for idempotency (updates if URL already exists)
    upsert_query = """
    INSERT INTO products 
    (url, title, is_available, price_pkr, is_call_for_price, description, categories, search_specs, display_specs, embedding)
    VALUES %s
    ON CONFLICT (url) DO UPDATE 
    SET title = EXCLUDED.title,
        is_available = EXCLUDED.is_available,
        price_pkr = EXCLUDED.price_pkr,
        is_call_for_price = EXCLUDED.is_call_for_price,
        description = EXCLUDED.description, 
        categories = EXCLUDED.categories,
        search_specs = EXCLUDED.search_specs,
        display_specs = EXCLUDED.display_specs,
        embedding = EXCLUDED.embedding;
    """

    # Prepare data for bulk execution
    data_list = []
    for item in dataset:
        embedding = item.get('embedding')
        if not embedding:
            continue
            
        data_list.append((
            item['url'],
            item['title'],
            item.get('is_available', True),
            item.get('pricing', {}).get('amount_pkr') if 'pricing' in item else item.get('price'),
            item.get('pricing', {}).get('is_call_for_price', False),
            item.get('description', ''),
            psycopg2.extras.Json(item.get('categories', [])),
            psycopg2.extras.Json(item.get('search_specs', {})),
            psycopg2.extras.Json(item.get('display_specs', {})),
            embedding
        ))

    print(f"🚀 Executing bulk upsert for {len(data_list)} products...")
    
    try:
        # execute_values is significantly faster than a for-loop for large datasets
        execute_values(cursor, upsert_query, data_list)
        conn.commit()
        print("✅ Database sync complete!")
    except Exception as e:
        conn.rollback()
        print(f"❌ Critical Database Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    load_data_to_db()