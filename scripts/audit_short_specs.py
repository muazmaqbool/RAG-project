import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

def audit_short_specs():
    print("🔍 Auditing database for sparse search specs...")
    
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT url, categories, search_specs FROM products WHERE search_specs IS NOT NULL;")
    products = cursor.fetchall()

    suspect_categories = {}

    for item in products:
        specs = item['search_specs']
        
        # Check if the dictionary has 3 or fewer keys
        if specs and len(specs.keys()) <= 5:
            cats = item['categories']
            
            # Extract the leaf category to group them cleanly
            if cats and isinstance(cats, list) and len(cats) > 0:
                leaf_cat = cats[0].split(">")[-1].strip()
            else:
                leaf_cat = "Unknown"

            if leaf_cat not in suspect_categories:
                suspect_categories[leaf_cat] = {
                    "count": 0, 
                    "example_url": item['url'], 
                    "keys_found": list(specs.keys())
                }
            
            suspect_categories[leaf_cat]["count"] += 1

    cursor.close()
    conn.close()

    if not suspect_categories:
        print("✅ All products have more than 3 search specs. You are good to go!")
        return

    print("\n⚠️  CATEGORIES WITH 3 OR FEWER SPECS:")
    print("-" * 50)
    for cat, data in suspect_categories.items():
        print(f"Category: {cat}")
        print(f"Products affected: {data['count']}")
        print(f"Extracted Keys: {data['keys_found']}")
        print(f"Example URL: {data['example_url']}")
        print("-" * 50)

if __name__ == "__main__":
    audit_short_specs()