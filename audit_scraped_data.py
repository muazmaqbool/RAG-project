import json
import os

# Point this to the raw output of your master_crawler.py
DATASET_FILE = 'data/raw/final_scraped_dataset.json'

def get_core_category(raw_cats):
    """Reusing your core category extraction logic to group stats accurately."""
    if not raw_cats:
        return "General"
        
    if isinstance(raw_cats, str):
        parts = [p.strip() for p in raw_cats.split('>')]
    elif isinstance(raw_cats, list):
        parts = []
        for item in raw_cats:
            parts.extend([p.strip() for p in str(item).split('>')])
    else:
        return "General"

    clean_parts = list(dict.fromkeys([p for p in parts if p]))
    final_path = []
    brand_only_parents = ["batteries", "chargers", "ssd", "new laptops", "used laptops", "laptops"] 
    
    for part in clean_parts:
        if part.lower() == "brands" or "brand" in part.lower():
            break
        final_path.append(part)
        if part.lower() in brand_only_parents:
            break

    if not final_path:
        return "Brand Only / Uncategorized"
        
    return " > ".join(final_path)

def audit_dataset():
    if not os.path.exists(DATASET_FILE):
        print(f"❌ Error: Could not find '{DATASET_FILE}'. Check the file path.")
        return

    print(f"🔍 Loading dataset from {DATASET_FILE}...")
    with open(DATASET_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Dictionary to hold our statistics
    # Structure: { "Category": {"total": 0, "short_desc": 0, "sparse_specs": 0} }
    stats = {}
    
    total_products = len(data)
    total_short_desc = 0
    total_sparse_specs = 0

    for item in data:
        # 1. Determine the category
        raw_cats = item.get('categories', [])
        core_cat = get_core_category(raw_cats)
        
        if core_cat not in stats:
            stats[core_cat] = {"total": 0, "short_desc": 0, "sparse_specs": 0}
            
        stats[core_cat]["total"] += 1

        # 2. Check Description Length (< 50 words)
        desc = item.get('description', '')
        word_count = len(desc.split())
        if word_count < 50:
            stats[core_cat]["short_desc"] += 1
            total_short_desc += 1

        # 3. Check Specifications Length (0 or 1 item)
        specs = item.get('specifications', {})
        if not isinstance(specs, dict) or len(specs) <= 1:
            stats[core_cat]["sparse_specs"] += 1
            total_sparse_specs += 1

    # --- PRINTING THE REPORT ---
    print("\n" + "="*80)
    print(f"{'CATEGORY':<45} | {'TOTAL':<6} | {'DESC < 50 WORDS':<15} | {'SPECS <= 1 ITEM'}")
    print("="*80)
    
    # Sort categories alphabetically for easier reading
    for cat in sorted(stats.keys()):
        data = stats[cat]
        
        # Calculate percentages to highlight severity
        desc_pct = (data['short_desc'] / data['total']) * 100 if data['total'] > 0 else 0
        spec_pct = (data['sparse_specs'] / data['total']) * 100 if data['total'] > 0 else 0
        
        desc_str = f"{data['short_desc']} ({desc_pct:.0f}%)"
        spec_str = f"{data['sparse_specs']} ({spec_pct:.0f}%)"
        
        # Truncate long category names to fit the table layout cleanly
        display_cat = cat[:42] + "..." if len(cat) > 45 else cat
        
        print(f"{display_cat:<45} | {data['total']:<6} | {desc_str:<15} | {spec_str}")

    print("="*80)
    print("📋 SUMMARY:")
    print(f"Total Products Audited: {total_products}")
    print(f"Total with Short Descriptions: {total_short_desc} ({(total_short_desc/total_products)*100:.1f}%)")
    print(f"Total with Sparse Specifications: {total_sparse_specs} ({(total_sparse_specs/total_products)*100:.1f}%)")
    print("="*80)

if __name__ == "__main__":
    audit_dataset()