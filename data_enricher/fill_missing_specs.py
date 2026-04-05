import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=os.getenv("FIREWORKS_API_KEY"),
)

# File Paths
DATASET_FILE = 'data/processed/enriched_dataset.json'  
SPECS_SCHEMA_FILE = 'data/processed/category_specifications.json' 
OUTPUT_FILE = 'data/processed/enriched_dataset_patched.json'

def extract_json_from_text(raw_text):
    try:
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            return json.loads(raw_text[start_idx:end_idx + 1])
        return None
    except Exception:
        return None

def get_core_category(raw_cats):
    if not raw_cats: return "General"
    parts = [p.strip() for p in raw_cats.split('>')] if isinstance(raw_cats, str) else [p.strip() for item in raw_cats for p in str(item).split('>')]
    clean_parts = list(dict.fromkeys([p for p in parts if p]))
    final_path = []
    brand_only_parents = ["batteries", "chargers", "ssd", "new laptops", "used laptops", "laptops"] 
    
    for part in clean_parts:
        if part.lower() == "brands" or "brand" in part.lower(): break
        final_path.append(part)
        if part.lower() in brand_only_parents: break
    return " > ".join(final_path) if final_path else None

def generate_missing_specs(title, description, valid_keys_list):
    prompt = f"""
    You are a strict data formatting engine. A product is missing its technical specifications.
    
    Product Title: {title}
    Product Description: {description}
    
    ALLOWED SPECIFICATION KEYS: {valid_keys_list}
    
    FATAL INSTRUCTIONS:
    1. You are STRICTLY FORBIDDEN from inventing new keys.
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
        parsed_json = extract_json_from_text(response.choices[0].message.content.strip())
        
        if parsed_json:
            # for k in list(parsed_json.keys()):
            #     if k not in valid_keys_list:
            #         print(f"      🚨 HARD REJECT: Model hallucinated key '{k}'. Dropping key.")
            #         del parsed_json[k] # Be forgiving: just drop the bad key instead of the whole object
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

    patched_dict = {item['url']: item for item in json.load(open(OUTPUT_FILE, 'r', encoding='utf-8'))} if os.path.exists(OUTPUT_FILE) else {}
    final_merged_dataset = []

    for index, raw_item in enumerate(raw_dataset):
        url = raw_item.get('url')
        if url in patched_dict and patched_dict[url].get('specifications'):
            final_merged_dataset.append(patched_dict[url])
            continue

        specs = raw_item.get('specifications')
        if not specs or len(specs) <= 1:
            categories = [raw_item.get('categories', [])] if isinstance(raw_item.get('categories', []), str) else raw_item.get('categories', [])
            core_cats_found = list(set([get_core_category(cat) for cat in categories if get_core_category(cat) in category_map]))
            
            valid_keys_for_this_item = master_list
            if core_cats_found:
                sets_of_keys = [set(category_map[c]) for c in core_cats_found]
                valid_keys_for_this_item = sorted(list(set.union(*sets_of_keys)))

            print(f"[{index + 1}/{len(raw_dataset)}] Extracting Specs: {raw_item.get('title', 'Unknown')[:40]}...")
            
            new_specs = generate_missing_specs(raw_item.get('title', ''), raw_item.get('description', ''), valid_keys_for_this_item)
            
            if new_specs:
                raw_item['specifications'] = new_specs
                
                # --- NEW: Re-calculate the mathematical embedding vector! ---
                embed_text = f"Title: {raw_item.get('title', '')}\nDescription: {raw_item.get('description', '')}\nSpecs: {json.dumps(new_specs)}"
                try:
                    vector_res = client.embeddings.create(model="nomic-ai/nomic-embed-text-v1.5", input=embed_text)
                    raw_item['embedding'] = vector_res.data[0].embedding
                except Exception as e:
                    print(f"   ⚠️ Failed to update embedding: {e}")
                # ------------------------------------------------------------
                
                print(f"   ✅ Mapped {len(new_specs)} specs.")
            else:
                print("   ⚠️ No valid specs extracted.")
            time.sleep(5.0) 
            
        final_merged_dataset.append(raw_item)
        
        if (index + 1) % 10 == 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f: json.dump(final_merged_dataset, f, indent=4)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_merged_dataset, f, indent=4)
    print(f"\n💾 Saved fully patched dataset to {OUTPUT_FILE}!")
        
if __name__ == "__main__":
    run_enrichment()