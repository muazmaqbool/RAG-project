import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_clean_leaf_categories():
    print("🔍 Building category tree with business logic overrides...")
    
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    cursor = conn.cursor()

    cursor.execute("SELECT categories FROM products WHERE categories IS NOT NULL;")
    rows = cursor.fetchall()

    # The brands we want to amputate from standard paths
    known_brands = {
        "acer", "amaze", "apple", "asus", "baseus", "dell", "earldom", 
        "hp", "ibm/lenovo", "lenovo", "mi (xiaomi)", "samsung", "ugreen", 
        "mix brands", "brands"
    }

    # NEW: The "Hard Stops" - If we see these, we stop going deeper and make them the leaf
    hard_stops = {"used laptops", "new laptops", "laptops"}

    all_clean_paths = set()

    # --- STEP 1: CLEAN AND NORMALIZE EVERY PATH ---
    for row in rows:
        cat_array = row[0]
        if not cat_array or not isinstance(cat_array, list):
            continue

        for path in cat_array:
            nodes = [n.strip() for n in path.split(">")]
            
            clean_nodes = []
            for node in nodes:
                node_lower = node.lower()
                
                # BUSINESS RULE: If it's a Laptop category, lock it in and ignore sub-categories
                if node_lower in hard_stops:
                    clean_nodes.append(node)
                    break 
                
                # If we hit a brand name, we stop building this path
                if node_lower in known_brands:
                    break
                    
                clean_nodes.append(node)
                
            if clean_nodes:
                all_clean_paths.add(tuple(clean_nodes))

    # --- STEP 2: BUILD THE GLOBAL TREE ---
    prefixes = set()
    for path in all_clean_paths:
        for i in range(1, len(path)):
            prefixes.add(path[:i])

    # --- STEP 3: EXTRACT TRUE TERMINAL LEAVES ---
    true_leaves = set()
    for path in all_clean_paths:
        if path not in prefixes:
            true_leaves.add(path[-1]) 

    cursor.close()
    conn.close()

    print("\n📋 YOUR CLEAN GLOBALLY UNIQUE LEAF CATEGORIES:")
    print("-" * 50)
    for cat in sorted(list(true_leaves)):
        print(f"- {cat}")
    print("-" * 50)
    print(f"Total Unique Clean Categories: {len(true_leaves)}\n")

if __name__ == "__main__":
    get_clean_leaf_categories()