import json
import os

# Point this to wherever your fully enriched JSON lives
DATASET_FILE = 'data/processed/enriched_dataset.json' 
OUTPUT_FILE = 'data/processed/unique_specifications.json'

def extract_unique_specs():
    if not os.path.exists(DATASET_FILE):
        print(f"❌ Error: Could not find '{DATASET_FILE}'. Please check the path.")
        return

    print("🔍 Reading dataset and extracting specification keys...")
    
    with open(DATASET_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    unique_keys = set()

    for item in data:
        specs = item.get('specifications', {})
        
        # Ensure specs is actually a dictionary before we try to loop through it
        if isinstance(specs, dict):
            for key in specs.keys():
                # Clean up the key: strip invisible whitespace and capitalize it 
                # This prevents "RAM", "Ram", and "ram " from counting as 3 different keys
                clean_key = key.strip().title()
                unique_keys.add(clean_key)

    # Sort them alphabetically so it's easy for us to read
    sorted_keys = sorted(list(unique_keys))

    # Save to a new JSON file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(sorted_keys, f, indent=4)

    print("\n" + "="*50)
    print(f"✅ Successfully extracted {len(sorted_keys)} unique specification keys!")
    print(f"📁 Saved to: {OUTPUT_FILE}")
    print("="*50)

if __name__ == "__main__":
    extract_unique_specs()