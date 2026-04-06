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
    extract_search_specs     # <--- Updated import
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
        (url, title, is_available, price_pkr, description, categories, search_specs, display_specs, embedding)
        VALUES %s 
        ON CONFLICT (url) DO UPDATE SET
            title = EXCLUDED.title, price_pkr = EXCLUDED.price_pkr, is_available = EXCLUDED.is_available,
            description = EXCLUDED.description, categories = EXCLUDED.categories,
            search_specs = EXCLUDED.search_specs, display_specs = EXCLUDED.display_specs, embedding = EXCLUDED.embedding;
    """
    
    values = [(i.get('url'), i.get('title', 'Unknown'), i.get('is_available', True), i.get('price'), 
               i.get('description', ''), psycopg2.extras.Json(i.get('categories', [])),
               psycopg2.extras.Json(i.get('search_specs', {})), psycopg2.extras.Json(i.get('display_specs', {})), 
               i.get('embedding')) for i in dataset if i.get('embedding')]

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

# --- THE 7-STEP CONTROLLER ---
def run_pipeline():
    print("🚀 Starting FULL Automated Pipeline...")
    
    # STEP 1: Get all URLs and scrape
    print("\n--- PHASE 1: Crawling ---")
    # build_master_list()
    # run_web_scraper()
    
    print("\n--- PHASE 2: AI ETL & Enrichment ---")
    master_db = {item['url']: item for item in load_json(DATABASE_JSON)}
    scrape = {item['url']: item for item in load_json(TODAYS_SCRAPE)}
    if not scrape:
        print("❌ Scrape empty. Aborting."); return
        
    schemas = load_json(SCHEMA_FILE)

    for index, (url, item) in enumerate(scrape.items()):
        title = item.get('title', 'Unknown')
        
        # STEP 2: Update existing entries
        if url in master_db:
            master_db[url]['price'] = item.get('price')
            master_db[url]['is_available'] = True
        
        # STEP 3: Categorize new entries
        else:
            print(f"   [{index+1}/{len(scrape)}] ✨ Processing New: {title[:40]}...")
            
            desc = item.get('description', '')
            specs = item.get('specifications', {})
            cat_path = item.get('categories', ['General'])[0] if item.get('categories') else "General"
            brand = cat_path.split(">")[-1].strip() if "Brands" in cat_path else ""
            word_count = len(desc.split())
            
            # STEP 5: DuckDuckGo for ghosts (No specs, no desc)
            if word_count < 50 and not specs:
                web_ctx = search_web_for_product(title, brand)
                ghost_data = hunt_ghost_data(title, web_ctx)
                if ghost_data.get('description') != 'Not found':
                    desc = ghost_data.get('description', '')
                    specs = ghost_data.get('specifications', {})
            
            # STEP 4: Get descriptions for missing descriptions but having specs
            elif word_count < 50 and specs:
                desc = draft_missing_description(specs, title)

            # STEP 6: Get search specs (And preserve raw specs as display specs!)
            target_schema = determine_schema(cat_path, schemas)
            strict_search_specs = extract_search_specs(title, desc, specs, target_schema)
            
            # --- VECTORIZATION ---
            embed_text = f"Title: {title}\nDescription: {desc}\nSpecs: {json.dumps(specs)}"
            embedding = generate_vector(embed_text)
            
            # --- ASSEMBLY ---
            item['description'] = desc
            item['search_specs'] = strict_search_specs
            item['display_specs'] = specs # Optimization applied here!
            item['embedding'] = embedding
            item['is_available'] = True
            
            if 'specifications' in item: del item['specifications']
            master_db[url] = item
            time.sleep(1) 

    # Soft Delete Missing Products
    for url in (set(master_db.keys()) - set(scrape.keys())):
        master_db[url]['is_available'] = False

    final_list = list(master_db.values())
    with open(DATABASE_JSON, 'w') as f: json.dump(final_list, f, indent=4)
    
    # STEP 7: Push new and updated entries to DB
    sync_to_postgres(final_list)
    print("🎉 System Perfectly Synced.")

if __name__ == "__main__":
    run_pipeline()