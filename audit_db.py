import os
import psycopg2
from psycopg2.extras import DictCursor
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

def run_database_audit():
    print("🔍 Scanning PostgreSQL Database for missing data...")
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    try:
        # Fetch all active products
        cursor.execute("""
            SELECT title, categories, description, search_specs, display_specs 
            FROM products 
            WHERE is_available = True
        """)
        rows = cursor.fetchall()
        
    finally:
        cursor.close()
        conn.close()

    if not rows:
        print("❌ No active products found in the database.")
        return

    # Dictionary to hold our statistics
    # Structure: { "Category Name": {"total": 0, "no_desc": 0, "no_search": 0, "no_display": 0} }
    stats = defaultdict(lambda: {"total": 0, "no_desc": 0, "no_search": 0, "no_display": 0})
    
    global_total = len(rows)
    global_no_desc = 0
    global_no_search = 0
    global_no_display = 0

    for row in rows:
        # 1. Determine the category (Grab the most specific leaf path)
        raw_cats = row['categories']
        if raw_cats and isinstance(raw_cats, list):
            # Takes the longest string, e.g., "Electronics > Laptops > HP" -> "HP"
            cat_name = max(raw_cats, key=len).split(">")[-1].strip()
        else:
            cat_name = "Uncategorized"

        # 2. Extract Fields
        desc = row.get('description') or ""
        search = row.get('search_specs') or {}
        display = row.get('display_specs') or {}

        # 3. Evaluate Emptiness
        is_empty_desc = desc.strip() == "" or desc.strip() == "Not found"
        is_empty_search = len(search) == 0
        is_empty_display = len(display) == 0

        # 4. Update Category Stats
        stats[cat_name]["total"] += 1
        if is_empty_desc: stats[cat_name]["no_desc"] += 1
        if is_empty_search: stats[cat_name]["no_search"] += 1
        if is_empty_display: stats[cat_name]["no_display"] += 1

        # 5. Update Global Stats
        if is_empty_desc: global_no_desc += 1
        if is_empty_search: global_no_search += 1
        if is_empty_display: global_no_display += 1

    # --- CLI TABLE FORMATTING ---
    print("\n" + "="*85)
    print(f"{'CATEGORY':<30} | {'TOTAL':<8} | {'NO DESC':<10} | {'NO SEARCH SPECS':<15} | {'NO DISPLAY SPECS':<15}")
    print("="*85)
    
    # Sort categories alphabetically for readability
    for cat, data in sorted(stats.items()):
        # Skip printing categories that are perfectly healthy to keep the terminal clean
        if data["no_desc"] == 0 and data["no_search"] == 0 and data["no_display"] == 0:
            continue
            
        print(f"{cat:<30} | {data['total']:<8} | {data['no_desc']:<10} | {data['no_search']:<15} | {data['no_display']:<15}")
        
    print("-" * 85)
    print(f"{'GLOBAL TOTALS (All Categories)':<30} | {global_total:<8} | {global_no_desc:<10} | {global_no_search:<15} | {global_no_display:<15}")
    print("="*85)
    
    # Quick Summary
    print(f"\n📊 Quick Summary:")
    print(f"  - Descriptions missing:  {round((global_no_desc / global_total) * 100, 1)}%")
    print(f"  - Search Specs missing:  {round((global_no_search / global_total) * 100, 1)}%")
    print(f"  - Display Specs missing: {round((global_no_display / global_total) * 100, 1)}%")

if __name__ == "__main__":
    run_database_audit()