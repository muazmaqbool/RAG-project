import os
import json
import time
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# --- MODULAR IMPORTS ---
from data_enricher.ai_toolkit import extract_search_specs

load_dotenv()

SCHEMA_FILE = 'data/processed/master_schema.json'

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

def reprocess_category():
    if not os.path.exists(SCHEMA_FILE):
        print(f"❌ Schema file missing: {SCHEMA_FILE}")
        return
        
    with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
        schemas = json.load(f)
        
    categories = list(schemas.keys())
    
    # --- 1. INTERACTIVE MENU ---
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=========================================")
    print("   🛠️ SCHEMA REPROCESSING TOOL")
    print("=========================================")
    for i, cat in enumerate(categories):
        print(f"[{i+1}] {cat}")
        
    choice = input(f"\nSelect the category number to reprocess (1-{len(categories)}): ")
    
    try:
        selected_cat = categories[int(choice) - 1]
        target_schema = schemas[selected_cat]
    except (ValueError, IndexError):
        print("❌ Invalid choice. Exiting.")
        return

    # --- 2. FETCH EXISTING DATA ---
    print(f"\n🔍 Fetching '{selected_cat}' products from database...")
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # NEW: Safely passing all wildcard strings as parameters to prevent % format errors
    cursor.execute("""
        SELECT url, title, description, display_specs 
        FROM products 
        WHERE categories::text ILIKE %s 
           OR categories::text ILIKE %s 
           OR categories::text ILIKE %s
    """, (f"%{selected_cat}%", '%powerbank%', '%power bank%'))
    
    products = cursor.fetchall()
    
    if not products:
        print(f"⚠️ No products found matching category: {selected_cat}")
        cursor.close()
        conn.close()
        return
        
    print(f"📦 Found {len(products)} products. Starting AI reprocessing...")
    
    # --- 3. RE-RUN AI EXTRACTION ---
    updates = []
    for index, item in enumerate(products):
        print(f"   [{index+1}/{len(products)}] Updating: {item['title'][:50]}...")
        
        # We pass the raw display_specs back into the LLM with the NEW target schema
        new_search_specs = extract_search_specs(
            title=item['title'],
            description=item['description'],
            raw_specs=item['display_specs'], 
            target_schema=target_schema
        )
        
        updates.append((psycopg2.extras.Json(new_search_specs), item['url']))
        time.sleep(1) # Protect against API rate limits
        
    # --- 4. BULK UPDATE POSTGRESQL ---
    print("\n💾 Saving new specs to PostgreSQL...")
    
    update_query = """
        UPDATE products 
        SET search_specs = %s 
        WHERE url = %s
    """
    
    try:
        psycopg2.extras.execute_batch(cursor, update_query, updates)
        conn.commit()
        print(f"🎉 Successfully reprocessed and updated {len(updates)} products!")
    except Exception as e:
        conn.rollback()
        print(f"❌ Database Update Failed: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    reprocess_category()