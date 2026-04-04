import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")

client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=FIREWORKS_API_KEY,
)

# File Paths
DATASET_FILE = 'data/processed/enriched_dataset.json'  
SPECS_SCHEMA_FILE = 'data/processed/category_specifications.json' 
OUTPUT_FILE = 'data/processed/enriched_dataset_patched.json'

def extract_json_from_text(raw_text):
    """Slices away conversational filler to isolate the JSON object."""
    try:
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            return json.loads(raw_text[start_idx:end_idx + 1])
        return None
    except Exception:
        return None

def get_core_category(raw_cats):
    """
    Extracts the functional product category.
    Stops at brand indicators or known brand-only parents.
    """
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

    # Order-Preserving Deduplication
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
        return None
        
    return " > ".join(final_path)

def generate_missing_specs(title, description, valid_keys_list):
    """Prompts Mixtral and enforces a STRICT Hard-Reject if any hallucination occurs."""
    prompt = f"""
    You are a strict data formatting engine. 
    A product is missing its technical specifications.
    
    Product Title: {title}
    Product Description: {description}
    
    ALLOWED SPECIFICATION KEYS: {valid_keys_list}
    
    FATAL INSTRUCTIONS:
    1. You are STRICTLY FORBIDDEN from inventing new keys. You cannot create new keys at all even if an information for it is present in the description.
    2. Every single key in your output MUST be an exact, character-for-character copy from the ALLOWED SPECIFICATION KEYS list.
    3. If you cannot confidently map a detail to an ALLOWED key, ignore it.
    
    Return EXACTLY a JSON object containing the mapped specifications.
    """
    
    try:
        response = client.chat.completions.create(
            model="accounts/fireworks/models/mixtral-8x22b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0 
        )
        raw_output = response.choices[0].message.content.strip()
        parsed_json = extract_json_from_text(raw_output)
        
        if parsed_json:
            for k in parsed_json.keys():
                if k not in valid_keys_list:
                    print(f"      🚨 HARD REJECT: Model hallucinated key '{k}'. Dropping entire result.")
                    return {} 
            return parsed_json
            
        return {}
    except Exception as e:
        print(f"API Error: {e}")
        return {}

def run_enrichment():
    if not os.path.exists(DATASET_FILE) or not os.path.exists(SPECS_SCHEMA_FILE):
        print("❌ Error: Files missing.")
        return

    with open(SPECS_SCHEMA_FILE, 'r', encoding='utf-8') as f:
        schema_data = json.load(f)
        category_map = schema_data.get("categories", {})
        master_list = schema_data.get("master_list", [])
        
    with open(DATASET_FILE, 'r', encoding='utf-8') as f:
        raw_dataset = json.load(f)

    patched_dict = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            for item in json.load(f):
                patched_dict[item['url']] = item

    updated_count = 0
    final_merged_dataset = []

    for index, raw_item in enumerate(raw_dataset):
        url = raw_item.get('url')
        existing_patched = patched_dict.get(url)
        
        if existing_patched and existing_patched.get('specifications') and len(existing_patched['specifications']) > 0:
            final_merged_dataset.append(existing_patched)
            continue

        specs = raw_item.get('specifications')
        
        if not specs or not isinstance(specs, dict) or len(specs) == 0:
            raw_cats = raw_item.get('categories', [])
            categories = [raw_cats] if isinstance(raw_cats, str) else raw_cats
            
            # 1. Collect all valid core categories for this item
            core_cats_found = []
            for cat in categories:
                core_cat = get_core_category(cat)
                if core_cat and core_cat in category_map:
                    core_cats_found.append(core_cat)
                    
            core_cats_found = list(set(core_cats_found))
            
            valid_keys_for_this_item = []
            
            # 2. THE SET INTERSECTION LOGIC
            if core_cats_found:
                # Create a list of sets containing the specs for each found category
                sets_of_keys = [set(category_map[c]) for c in core_cats_found]
                
                # Perform an intersection to find the common keys across ALL mentioned categories
                intersected_keys = set.intersection(*sets_of_keys)
                
                # Fallback: If categories completely clash and have 0 overlap, fallback to union to be safe
                if not intersected_keys:
                    intersected_keys = set.union(*sets_of_keys)
                    
                valid_keys_for_this_item = sorted(list(intersected_keys))
            
            # 3. Final Fallback
            if not valid_keys_for_this_item:
                valid_keys_for_this_item = master_list

            print(f"[{index + 1}/{len(raw_dataset)}] Patching: {raw_item.get('title', 'Unknown')[:40]}... (Using {len(valid_keys_for_this_item)} strict keys)")
            
            new_specs = generate_missing_specs(
                title=raw_item.get('title', ''),
                description=raw_item.get('description', ''),
                valid_keys_list=valid_keys_for_this_item
            )
            
            if new_specs:
                raw_item['specifications'] = new_specs
                updated_count += 1
                print(f"   ✅ Added {len(new_specs)} pure specs.")
            else:
                print("   ⚠️ No valid specs extracted or generation was rejected.")
                
            # THE RATE LIMIT DELAY (Using 5 seconds for safety)
            print("   ⏳ Waiting 2 seconds for API limits...")
            time.sleep(2.0) 
            
        final_merged_dataset.append(raw_item)

    print(f"\n💾 Saving {len(final_merged_dataset)} total products to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_merged_dataset, f, indent=4)
        
if __name__ == "__main__":
    run_enrichment()