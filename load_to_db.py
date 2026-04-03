import json
import os
import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_PASSWORD = os.getenv("DB_PASSWORD")

# Postgres connection parameters
DB_PARAMS = {
    "dbname": "postgres",
    "user": "postgres",
    "password": DB_PASSWORD,
    "host": "localhost",
    "port": "5432"
}

ENRICHED_FILE = 'data/processed/enriched_dataset.json'

def get_db_connection():
    """Connects to Postgres and enables vector math support."""
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(**DB_PARAMS)
    register_vector(conn)
    return conn

def load_data_to_db():
    if not os.path.exists(ENRICHED_FILE):
        print(f"Error: Could not find {ENRICHED_FILE}. Did you run the enrichment scripts?")
        return

    print("Loading enriched JSON dataset into memory...")
    with open(ENRICHED_FILE, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    conn = get_db_connection()
    cursor = conn.cursor()

    print(f"Starting bulk database insertion for {len(dataset)} products...")
    
    # We use ON CONFLICT DO UPDATE so this script is idempotent (safe to run multiple times)
    query = """
    INSERT INTO products 
    (url, title, is_available, price_pkr, is_call_for_price, description, categories, specifications, embedding)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (url) DO UPDATE 
    SET title = EXCLUDED.title,
        is_available = EXCLUDED.is_available,
        price_pkr = EXCLUDED.price_pkr,
        is_call_for_price = EXCLUDED.is_call_for_price,
        description = EXCLUDED.description, 
        categories = EXCLUDED.categories,
        specifications = EXCLUDED.specifications,
        embedding = EXCLUDED.embedding;
    """

    success_count = 0
    error_count = 0

    for item in dataset:
        try:
            # Safely grab the embedding; skip if it failed during enrichment
            embedding = item.get('embedding')
            if not embedding:
                print(f"  [!] Skipping {item['title']}: No vector embedding found.")
                continue

            cursor.execute(query, (
                item['url'],
                item['title'],
                item.get('is_available', True),
                item.get('pricing', {}).get('amount_pkr'),
                item.get('pricing', {}).get('is_call_for_price', False),
                item.get('description', ''),
                psycopg2.extras.Json(item.get('categories', [])),
                psycopg2.extras.Json(item.get('specifications', {})),
                embedding
            ))
            success_count += 1
            
        except Exception as e:
            print(f"  [!] Database Insertion Error on {item['title']}: {e}")
            conn.rollback() # Rollback the current transaction on error
            error_count += 1
            continue

    # Commit all successful inserts
    conn.commit()
    cursor.close()
    conn.close()

    print("\n✅ Database Loading Complete!")
    print(f"   -> Successfully inserted/updated: {success_count}")
    print(f"   -> Errors skipped: {error_count}")

if __name__ == "__main__":
    load_data_to_db()