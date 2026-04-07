import os
import json
import time
import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector
from openai import OpenAI
from dotenv import load_dotenv

# --- MODULAR IMPORTS ---
from scrapers.url_crawler import build_master_list
from scrapers.master_crawler import run_web_scraper
from data_enricher.ai_toolkit import (
    search_web_for_product, 
    hunt_ghost_data, 
    draft_missing_description, 
    generate_vector,
    determine_schema,        
    extract_search_specs     
)

load_dotenv()
client = OpenAI(base_url="https://api.fireworks.ai/inference/v1", api_key=os.getenv("FIREWORKS_API_KEY"))

TODAYS_SCRAPE = 'data/raw/todays_scrape.json'
DATABASE_JSON = 'data/processed/dual_layer_dataset.json'
SCHEMA_FILE = 'data/processed/master_schema.json'

def load_json(path):
    return json.load(open(path, 'r', encoding='utf-8')) if os.path.exists(path) else []

# --- DATABASE SYNC ---
def sync_to_postgres(dataset):
    print("🔌 Syncing to PostgreSQL...")
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"), host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432")
    )
    register_vector(conn)
    cursor = conn.cursor()

    query = """
        INSERT INTO products 
        (url, title, is_available, price_pkr, is_call_for_price, description, categories, search_specs, display_specs, embedding)
        VALUES %s 
        ON CONFLICT (url) DO UPDATE SET
            title = EXCLUDED.title, price_pkr = EXCLUDED.price_pkr, 
            is_available = EXCLUDED.is_available, is_call_for_price = EXCLUDED.is_call_for_price,
            description = EXCLUDED.description, categories = EXCLUDED.categories,
            search_specs = EXCLUDED.search_specs, display_specs = EXCLUDED.display_specs, 
            embedding = EXCLUDED.embedding;
    """
    
    # We grab `price` and `is_call_for_price` safely from the dataset
    values = [(
        i.get('url'), 
        i.get('title', 'Unknown'), 
        i.get('is_available', True), 
        i.get('price'), 
        i.get('is_call_for_price', False), 
        i.get('description', ''), 
        psycopg2.extras.Json(i.get('categories', [])),
        psycopg2.extras.Json(i.get('search_specs', {})), 
        psycopg2.extras.Json(i.get('display_specs', {})), 
        i.get('embedding')
    ) for i in dataset if i.get('embedding')]

    try:
        execute_values(cursor, query, values)
        conn.commit()
        print(f"✅ Synced {len(values)} products.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Database Sync Failed: {e}")
    finally:
        cursor.close()
        conn.close()

# --- PHASE 2: AI ETL LOGIC ---
def run_ai_enrichment():
    master_db = {item['url']: item for item in load_json(DATABASE_JSON)}
    scrape = {item['url']: item for item in load_json(TODAYS_SCRAPE)}
    
    if not scrape:
        print("❌ Scrape empty. Run Step 2 first."); return
        
    schemas = load_json(SCHEMA_FILE)
    new_items_processed = 0

    for index, (url, item) in enumerate(scrape.items()):
        title = item.get('title', 'Unknown')
        
        # Check if it's already in our DB and fully enriched (has embedding)
        if url in master_db and master_db[url].get('embedding'):
            # Just update fast-changing data
            price_val = item.get('price')
            master_db[url]['price'] = price_val
            master_db[url]['is_call_for_price'] = True if price_val is None else False
            master_db[url]['is_available'] = True
            continue # Skip AI processing
            
        print(f"   [{index+1}/{len(scrape)}] ✨ AI Processing: {title[:40]}...")
        
        desc = item.get('description', '')
        specs = item.get('specifications', {})
        # NEW: Smash the entire array into one giant lowercase string for foolproof searching
        raw_cats = item.get('categories', [])
        cat_string = " | ".join(raw_cats).lower() if raw_cats else "general"
        
        # We still need a single path for the schema target, taking the longest/most specific one
        cat_path = max(raw_cats, key=len) if raw_cats else "General" 
        brand = cat_path.split(">")[-1].strip() if "Brands" in cat_path else ""
        word_count = len(desc.split())
        
        # AI Tools
        if word_count < 50 and not specs:
            web_ctx = search_web_for_product(title, brand)
            ghost_data = hunt_ghost_data(title, web_ctx)
            if ghost_data.get('description') != 'Not found':
                desc = ghost_data.get('description', '')
                specs = ghost_data.get('specifications', {})
        
        elif word_count < 50 and specs:
            desc = draft_missing_description(specs, title)

        target_schema = determine_schema(cat_string, schemas)
        strict_search_specs = extract_search_specs(title, desc, specs, target_schema)
        
        embed_text = f"Title: {title}\nDescription: {desc}\nSpecs: {json.dumps(specs)}"
        embedding = generate_vector(embed_text)
        
        # Assembly
        price_val = item.get('price')
        item['price'] = price_val
        item['is_call_for_price'] = True if price_val is None else False
        item['description'] = desc
        item['search_specs'] = strict_search_specs
        item['display_specs'] = specs 
        item['embedding'] = embedding
        item['is_available'] = True
        
        if 'specifications' in item: del item['specifications']
        
        master_db[url] = item
        new_items_processed += 1
        
        # --- THE CTRL+C SAVIOR: Save every 5 items ---
        if new_items_processed % 5 == 0:
            print("   💾 Saving state...")
            with open(DATABASE_JSON, 'w') as f: 
                json.dump(list(master_db.values()), f, indent=4)
        time.sleep(2) 

    # Final Soft Delete & Save
    for url in (set(master_db.keys()) - set(scrape.keys())):
        master_db[url]['is_available'] = False

    with open(DATABASE_JSON, 'w') as f: 
        json.dump(list(master_db.values()), f, indent=4)
    print("🎉 AI Enrichment Complete.")

# --- THE INTERACTIVE DASHBOARD ---
def interactive_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear') # Clears the terminal
        print("=========================================")
        print("   🤖 E-COMMERCE RAG CONTROL PANEL")
        print("=========================================")
        
        # Calculate pending items
        master_urls = load_json('data/raw/master_product_urls.json')
        todays_scrape = load_json(TODAYS_SCRAPE)
        master_db = load_json(DATABASE_JSON)
        
        total_urls = len(master_urls) if master_urls else 0
        scraped_count = len(todays_scrape) if todays_scrape else 0
        
        # Count items in DB that actually have an embedding (fully processed)
        enriched_count = sum(1 for item in master_db if item.get('embedding'))
        
        pending_scrape = total_urls - scraped_count
        pending_ai = scraped_count - enriched_count
        
        print(f"📊 SYSTEM STATUS:")
        print(f"  - URLs Found: {total_urls}")
        print(f"  - Items Scraped: {scraped_count} (Pending: {max(0, pending_scrape)})")
        print(f"  - Items AI Enriched: {enriched_count} (Pending: {max(0, pending_ai)})")
        print("=========================================")
        
        print("\n[1] Find URLs (build_master_list)")
        print(f"[2] Scrape HTML (run_web_scraper) -> Resumes automatically")
        print(f"[3] Run AI Pipeline -> Resumes automatically")
        print("[4] Sync to PostgreSQL Database")
        print("[5] Run FULL Pipeline (1 through 4)")
        print("[0] Exit")
        
        choice = input("\nSelect a step to run: ")
        
        if choice == '1':
            build_master_list()
            input("\nPress Enter to return to menu...")
        elif choice == '2':
            run_web_scraper()
            input("\nPress Enter to return to menu...")
        elif choice == '3':
            run_ai_enrichment()
            input("\nPress Enter to return to menu...")
        elif choice == '4':
            sync_to_postgres(load_json(DATABASE_JSON))
            input("\nPress Enter to return to menu...")
        elif choice == '5':
            build_master_list()
            run_web_scraper()
            run_ai_enrichment()
            sync_to_postgres(load_json(DATABASE_JSON))
            input("\nPress Enter to return to menu...")
        elif choice == '0':
            print("Exiting...")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    interactive_menu()