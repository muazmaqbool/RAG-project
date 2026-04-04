import json
import os

DATASET_FILE = 'data/processed/enriched_dataset.json' 
OUTPUT_FILE = 'data/processed/category_specifications.json'

def get_core_category(raw_cats):
    if not raw_cats:
        return "General"
        
    # 1. Parse into a flat list
    if isinstance(raw_cats, str):
        parts = [p.strip() for p in raw_cats.split('>')]
    elif isinstance(raw_cats, list):
        parts = []
        for item in raw_cats:
            parts.extend([p.strip() for p in str(item).split('>')])
    else:
        return "General"

    # 2. Order-Preserving Deduplication (fixes "Acc > Mob Acc > Acc > Mob Acc")
    clean_parts = list(dict.fromkeys([p for p in parts if p]))
    
    # 3. THE NEW TRAVERSAL LOGIC
    final_path = []
    
    # Categories where we know the immediate next level is just a brand name
    brand_only_parents = [
        "batteries", 
        "chargers", 
        "ssd", 
        "new laptops", 
        "used laptops", 
        "laptops"
    ] 
    
    for part in clean_parts:
        # If we explicitly hit a "Brands" node, stop immediately. Do not include it.
        if part.lower() == "brands" or "brand" in part.lower():
            break
            
        final_path.append(part)
        
        # If we just appended a category like "Batteries", we know the NEXT item 
        # in the loop will be a brand. So, we break now to prevent appending it.
        if part.lower() in brand_only_parents:
            break

    # If the entire path was just "Brands > Amaze", final_path will be empty
    if not final_path:
        return None
        
    # Rejoin the path gracefully! 
    # Example: ["Accessories", "Mobile Accessories", "Power Banks"] -> "Accessories > Mobile Accessories > Power Banks"
    return " > ".join(final_path)

def extract_category_specs():
    if not os.path.exists(DATASET_FILE):
        print(f"❌ Error: Could not find '{DATASET_FILE}'.")
        return

    print("🔍 Reading dataset and extracting core category-mapped specifications...")
    
    with open(DATASET_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    category_specs = {}
    master_specs = set()

    for item in data:
        specs = item.get('specifications', {})
        raw_cats = item.get('categories', [])
        
        categories = [raw_cats] if isinstance(raw_cats, str) else raw_cats

        if isinstance(specs, dict) and len(specs) > 0:
            for cat in categories:
                core_cat = get_core_category(cat)
                
                # If the function returned None (because it was a Brand), skip it!
                if not core_cat:
                    continue
                    
                if core_cat not in category_specs:
                    category_specs[core_cat] = set()
                
                for key in specs.keys():
                    clean_key = key.strip().title()
                    category_specs[core_cat].add(clean_key)
                    master_specs.add(clean_key)

    final_output = {
        "master_list": sorted(list(master_specs)),
        "categories": {k: sorted(list(v)) for k, v in category_specs.items()}
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=4)

    print("\n" + "="*50)
    print(f"✅ Extracted {len(master_specs)} master keys mapped across {len(category_specs)} core categories!")
    print(f"📁 Saved to: {OUTPUT_FILE}")
    print("="*50)

if __name__ == "__main__":
    extract_category_specs()