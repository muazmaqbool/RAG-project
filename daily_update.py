import os
import json
import time
import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector
from openai import OpenAI
from dotenv import load_dotenv
import threading
from queue import Queue

# --- MODULAR IMPORTS ---
from scrapers.url_crawler import build_master_list
from scrapers.master_crawler import run_web_scraper, scrape_product_data
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

import tempfile

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []
    
def atomic_save_json(data, target_path):
    """Safely saves JSON to a temp file first, then atomically replaces the target file."""
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(target_path), suffix='.json')
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, indent=4)
    os.replace(tmp_path, target_path)

def load_and_clean_db(path):
    """Loads database, aggressively purges corrupted arrays and Unkown titles, and returns dict."""
    raw_data = load_json(path)
    clean_db = []
    purged = 0
    
    for item in raw_data:
        if not isinstance(item, dict) or 'url' not in item:
            purged += 1
            continue
            
        title = item.get('title', 'Unknown')
        if title == 'Unknown' or not title.strip():
            purged += 1
            continue
            
        emb = item.get('embedding', [])
        if emb and len(emb) != 768:
            purged += 1
            continue
            
        clean_db.append(item)
        
    if purged > 0:
        print(f"🧹 [Auto-Heal] Vacuumed {purged} corrupted/stub items from DB.")
        atomic_save_json(clean_db, path)
        
    # Optional logic: Convert immediately to indexed dict or let the caller do it?
    # Caller does it. Returns list of dicts.
    return clean_db

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
        (url, title, is_available, price_pkr, is_call_for_price, description, categories, search_specs, display_specs, embedding, image_url, leaf_category)
        VALUES %s 
        ON CONFLICT (url) DO UPDATE SET
            title = EXCLUDED.title, price_pkr = EXCLUDED.price_pkr, 
            is_available = EXCLUDED.is_available, is_call_for_price = EXCLUDED.is_call_for_price,
            description = EXCLUDED.description, categories = EXCLUDED.categories,
            search_specs = EXCLUDED.search_specs, display_specs = EXCLUDED.display_specs, 
            embedding = EXCLUDED.embedding, image_url = EXCLUDED.image_url, leaf_category = EXCLUDED.leaf_category;
    """
    
    # Helper to extract the leaf category
    def get_leaf(cat_list):
        if not cat_list: return "General"
        
        longest_path = max(cat_list, key=len)
        parts = [p.strip() for p in longest_path.split(">")]
        
        # --- THE OVERRIDE: Group all laptops by their parent category ---
        # If the path is "Home > Used Laptops > HP", this stops at "Used Laptops"
        for part in parts:
            if "Laptops" in part:
                return part
                
        # Default behavior for everything else (e.g., grabs "Wireless Mice" from the end)
        return parts[-1]

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
        i.get('embedding'),
        i.get('image_url'),
        get_leaf(i.get('categories', [])) # <--- NEW EXPLICIT COLUMN
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

def sync_history_to_postgres(changelog):
    if not changelog:
        return
        
    print(f"📝 Saving {len(changelog)} history events to database...")
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"), user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"), host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432")
    )
    cursor = conn.cursor()
    
    query = """
        INSERT INTO product_history (url, action, old_price, new_price)
        VALUES %s
    """
    try:
        execute_values(cursor, query, changelog)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ History Sync Failed: {e}")
    finally:
        cursor.close()
        conn.close()

# --- PHASE 2: AI ETL LOGIC ---
def run_ai_enrichment():
    master_db = {item['url']: item for item in load_and_clean_db(DATABASE_JSON)}
    scrape = {item['url']: item for item in load_json(TODAYS_SCRAPE)}
    
    if not scrape:
        print("❌ Scrape empty. Run Step 2 first."); return
        
    schemas = load_json(SCHEMA_FILE)
    ignored_categories = load_json('data/ignored_categories.json')
    new_items_processed = 0
    changelog = []

    for index, (url, item) in enumerate(scrape.items()):
        raw_cats = item.get('categories', [])
        categories_str = " | ".join(raw_cats).lower() if raw_cats else ""
        search_str = (url + " " + categories_str).lower()
        if ignored_categories and any(ig.lower() in search_str for ig in ignored_categories):
            continue
            
        title = item.get('title', 'Unknown')
        
        db_item = master_db.get(url, {})
        new_price = item.get('price')
        
        # --- NEW: History Logic ---
        if db_item:
            old_price = db_item.get('price')
            if old_price != new_price:
                changelog.append((url, 'PRICE_CHANGED', old_price, new_price))
        else:
            changelog.append((url, 'ADDED', None, new_price))
            
        db_title = db_item.get('title', '')
        is_title_valid = bool(db_title) and db_title != 'Unknown'
        
        if db_item and db_item.get('embedding') and is_title_valid:
            # Just update fast-changing data
            price_val = item.get('price')
            master_db[url]['price'] = price_val
            master_db[url]['is_call_for_price'] = True if price_val is None else False
            master_db[url]['is_available'] = True
            
            # Non-breaking changes like updated titles or images should be synced directly
            if item.get('title') and item.get('title') != 'Unknown':
                master_db[url]['title'] = item.get('title')
            if item.get('image_url'):
                master_db[url]['image_url'] = item.get('image_url')
                
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
                generated_desc = ghost_data.get('description', '')
                # Append the generated text to the original short description
                desc = f"{desc}\n\n{generated_desc}".strip()
                specs = ghost_data.get('specifications', {})
        
        elif word_count < 50 and specs:
            generated_desc = draft_missing_description(specs, title)
            # Append the generated text to the original short description
            desc = f"{desc}\n\n{generated_desc}".strip()

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
            atomic_save_json(list(master_db.values()), DATABASE_JSON)
        time.sleep(2) 

    # Final Soft Delete & Save
    for url in (set(master_db.keys()) - set(scrape.keys())):
        if master_db[url].get('is_available', True):
            old_price = master_db[url].get('price')
            changelog.append((url, 'REMOVED', old_price, None))
            master_db[url]['is_available'] = False

    atomic_save_json(list(master_db.values()), DATABASE_JSON)
        
    print("🎉 AI Enrichment Complete.")
    if changelog:
        sync_history_to_postgres(changelog)

# --- PHASE 3: THE PARALLEL PIPELINE (OPTION 3) ---
def run_parallel_pipeline():
    print("🚀 Starting Parallel Pipeline (Scraper + AI)...")
    
    master_db = {item['url']: item for item in load_and_clean_db(DATABASE_JSON)}
    url_dict = load_json('data/raw/master_product_urls.json')
    schemas = load_json(SCHEMA_FILE)
    ignored_categories = load_json('data/ignored_categories.json')
    
    if not url_dict:
        print("❌ Master URLs missing. Run Step 1 first.")
        return

    choice = input("Do you want to [R]esume a partial run or start a [F]resh full daily update? (r/f): ").strip().lower()

    pipeline_queue = Queue(maxsize=20)
    changelog = [] # <--- NEW: The global ledger for this run
    db_lock = threading.Lock()

    # --- PRODUCER: The Scraper Thread ---
    def scraper_worker():
        count = 0
        new_items_sent_to_ai = 0
        total_urls = len(url_dict)
        
        for url, categories in url_dict.items():
            count += 1
            print(f"  🕷️ [Scraper] Fast-scanning {count}/{total_urls} URLs: {url}")
            
            # --- RESUME LOGIC ---
            if choice == 'r' and url in master_db:
                db_item = master_db[url]
                db_title = db_item.get('title', '')
                is_title_valid = bool(db_title) and db_title != 'Unknown'
                # If fully enriched, skip scraping it entirely to recover from the crash swiftly!
                if db_item.get('embedding') and db_item.get('search_specs') and is_title_valid:
                    continue
            
            categories_str = " | ".join(categories).lower() if categories else ""
            search_str = (url + " " + categories_str).lower()
            if ignored_categories and any(ig.lower() in search_str for ig in ignored_categories):
                continue
                
            data = scrape_product_data(url, categories)
            new_price = data.get('price')
            
            # --- THE INTERCEPTOR: Detect Changes ---
            if url in master_db:
                old_price = master_db[url].get('price')
                
                # Check for Price Change
                if old_price != new_price:
                    changelog.append((url, 'PRICE_CHANGED', old_price, new_price))
                    
                db_title = master_db[url].get('title', '')
                is_title_valid = bool(db_title) and db_title != 'Unknown'
                
                if master_db[url].get('embedding') and master_db[url].get('search_specs') and is_title_valid:
                    master_db[url]['price'] = new_price
                    master_db[url]['is_call_for_price'] = data.get('is_call_for_price')
                    master_db[url]['is_available'] = True
                    
                    if data.get('title') and data.get('title') != 'Unknown':
                        master_db[url]['title'] = data.get('title')
                    if data.get('image_url'):
                        master_db[url]['image_url'] = data.get('image_url')
                else:
                    # Re-route to AI worker if missing something critical
                    pipeline_queue.put((url, data))
                    new_items_sent_to_ai += 1
            else:
                # It's a completely new item!
                changelog.append((url, 'ADDED', None, new_price))
                pipeline_queue.put((url, data))
                new_items_sent_to_ai += 1
                
            time.sleep(0.5) 
            
        print(f"🛑 Scraper finished! Sent {new_items_sent_to_ai} items to AI out of {count} total URLs.")

    # --- CONSUMER: The AI Thread ---
    def ai_worker():
        processed_count = 0
        while True:
            payload = pipeline_queue.get()
            if payload is None: # We received the poison pill
                break
                
            url, item = payload
            title = item.get('title', 'Unknown')
            print(f"  ✨ [AI Worker] Processing: {title[:40]}...")
            
            desc = item.get('description', '')
            specs = item.get('specifications', {})
            raw_cats = item.get('categories', [])
            cat_string = " | ".join(raw_cats).lower() if raw_cats else "general"
            cat_path = max(raw_cats, key=len) if raw_cats else "General" 
            brand = cat_path.split(">")[-1].strip() if "Brands" in cat_path else ""
            word_count = len(desc.split())
            
            # AI Toolkit Logic
            if word_count < 50 and not specs:
                web_ctx = search_web_for_product(title, brand)
                ghost_data = hunt_ghost_data(title, web_ctx)
                if ghost_data.get('description') != 'Not found':
                    generated_desc = ghost_data.get('description', '')
                    desc = f"{desc}\n\n{generated_desc}".strip()
                    specs = ghost_data.get('specifications', {})
            elif word_count < 50 and specs:
                generated_desc = draft_missing_description(specs, title)
                desc = f"{desc}\n\n{generated_desc}".strip()

            target_schema = determine_schema(cat_string, schemas)
            strict_search_specs = extract_search_specs(title, desc, specs, target_schema)
            
            embed_text = f"Title: {title}\nDescription: {desc}\nSpecs: {json.dumps(specs)}"
            embedding = generate_vector(embed_text)
            
            # Assemble the final product
            item['description'] = desc
            item['search_specs'] = strict_search_specs
            item['display_specs'] = specs 
            item['embedding'] = embedding
            if 'specifications' in item: del item['specifications']
            
            # Update master memory
            with db_lock:
                master_db[url] = item
            processed_count += 1
            
            # Save state every 5 items so you don't lose progress if you crash
            if processed_count % 5 == 0:
                print("  💾 [AI Worker] Saving state to JSON...")
                with db_lock:
                    atomic_save_json(list(master_db.values()), DATABASE_JSON)
                    
            pipeline_queue.task_done()

        # Final save when the queue is completely empty
        with db_lock:
            atomic_save_json(list(master_db.values()), DATABASE_JSON)
        print("🎉 AI Worker finished processing all queued items.")

    # --- EXECUTE THE THREADS ---
    t1 = threading.Thread(target=scraper_worker)
    
    num_ai_workers = 10
    ai_threads = [threading.Thread(target=ai_worker) for _ in range(num_ai_workers)]
    
    t1.start()
    for t in ai_threads:
        t.start()
    
    t1.join()
    
    # Send enough poison pills for all workers to shut down since the scraper is done
    for _ in range(num_ai_workers):
        pipeline_queue.put(None)
        
    for t in ai_threads:
        t.join()
    
    print("🧹 Performing soft-delete check for removed products...")
    for db_url in master_db.keys():
        if db_url not in url_dict and master_db[db_url].get('is_available', True):
            # It was available, but now it's gone
            old_price = master_db[db_url].get('price')
            changelog.append((db_url, 'REMOVED', old_price, None))
            master_db[db_url]['is_available'] = False
            
    # Sync everything to PostgreSQL
    sync_to_postgres(list(master_db.values()))
    sync_history_to_postgres(changelog) # <--- NEW: Save the ledger
    print("✅ Parallel run complete and synced to database!")

# --- PHASE 4: THE MOP-UP CREW (AI RETRY) ---
def retry_failed_ai():
    print("🔄 Scanning database for failed AI enrichments...")
    master_db = {item['url']: item for item in load_and_clean_db(DATABASE_JSON)}
    schemas = load_json(SCHEMA_FILE)
    
    # Deep Clean: Find items missing embeddings OR missing search/display specs
    failed_urls = []
    for url, item in master_db.items():
        has_vector = bool(item.get('embedding'))
        has_search = bool(item.get('search_specs'))
        has_title = bool(item.get('title')) and item.get('title') != 'Unknown'

        # If any of the core pillars are missing, flag it for retry
        if not has_vector or not has_search or not has_title:
            failed_urls.append(url)
    
    if not failed_urls:
        print("✅ No failed items found! Your database is fully enriched.")
        return
        
    print(f"🛠️ Found {len(failed_urls)} incomplete items. Retrying AI without scraping...")
    
    for index, url in enumerate(failed_urls):
        item = master_db[url]
        title = item.get('title', 'Unknown')
        print(f"   [{index+1}/{len(failed_urls)}] ✨ Retrying: {title[:40]}...")
        
        desc = item.get('description', '')
        specs = item.get('display_specs', {}) # Pull from what we already saved
        raw_cats = item.get('categories', [])
        cat_string = " | ".join(raw_cats).lower() if raw_cats else "general"
        cat_path = max(raw_cats, key=len) if raw_cats else "General" 
        brand = cat_path.split(">")[-1].strip() if "Brands" in cat_path else ""
        word_count = len(desc.split())
        
        # AI Toolkit Logic
        if word_count < 50 and not specs:
            web_ctx = search_web_for_product(title, brand)
            ghost_data = hunt_ghost_data(title, web_ctx)
            if ghost_data.get('description') != 'Not found':
                generated_desc = ghost_data.get('description', '')
                desc = f"{desc}\n\n{generated_desc}".strip()
                specs = ghost_data.get('specifications', {})
        elif word_count < 50 and specs:
            generated_desc = draft_missing_description(specs, title)
            desc = f"{desc}\n\n{generated_desc}".strip()

        target_schema = determine_schema(cat_string, schemas)
        strict_search_specs = extract_search_specs(title, desc, specs, target_schema)
        
        embed_text = f"Title: {title}\nDescription: {desc}\nSpecs: {json.dumps(specs)}"
        embedding = generate_vector(embed_text)
        
        # Update the item
        item['description'] = desc
        item['search_specs'] = strict_search_specs
        item['display_specs'] = specs 
        item['embedding'] = embedding
        
        master_db[url] = item
        
        # Save state every 5 items
        if (index + 1) % 5 == 0:
            print("  💾 Saving state to JSON...")
            atomic_save_json(list(master_db.values()), DATABASE_JSON)
                
        time.sleep(2) # Respect API rate limits

    # Final save and sync
    atomic_save_json(list(master_db.values()), DATABASE_JSON)
    
    sync_to_postgres(list(master_db.values()))
    print("🎉 AI Retry Complete and synced to database!")

def manage_ignored_categories():
    ignore_file = 'data/ignored_categories.json'
    ignored = load_json(ignore_file)
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=========================================")
        print("   🚫 SETTINGS: IGNORED CATEGORIES")
        print("=========================================")
        if not ignored:
            print("  No categories currently ignored.")
        else:
            print("  Currently Ignored Keywords:")
            for idx, keyword in enumerate(ignored):
                print(f"    - {keyword}")
        print("=========================================")
        
        choice = input("\nEnter a keyword to toggle its ignore status (or type '0' to return): ").strip()
        
        if choice == '0':
            break
        elif choice:
            keyword_lower = choice.lower()
            existing = [k for k in ignored if k.lower() == keyword_lower]
            if existing:
                ignored.remove(existing[0])
                print(f"\n✅ Removed '{existing[0]}' from ignore list.")
            else:
                ignored.append(choice)
                print(f"\n✅ Added '{choice}' to ignore list.")
            atomic_save_json(ignored, 'data/ignored_categories.json')
            time.sleep(1)

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
        master_db = load_and_clean_db(DATABASE_JSON)
        
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
        
        print("[1] 🗺️ Map Website URLs (Updates Master List)")
        print("[2] 🚀 Run FULL Daily Update (Parallel Scrape + AI + DB Sync)")
        print("[3] 🛠️ Retry Failed AI Tasks (No Scraping)")
        print("[4] ⚙️ Settings: Manage Ignored Categories")
        print("[0] Exit")
        
        choice = input("\nSelect a step to run: ")
        
        if choice == '1':
            build_master_list()
            input("\nPress Enter to return to menu...")
        elif choice == '2':
            run_parallel_pipeline()
            input("\nPress Enter to return to menu...")
        elif choice == '3':
            retry_failed_ai()
            input("\nPress Enter to return to menu...")
        elif choice == '4':
            manage_ignored_categories()
        elif choice == '0':
            print("Exiting...")
            break
        else:
            print("Invalid choice.")
            time.sleep(1)

if __name__ == "__main__":
    interactive_menu()