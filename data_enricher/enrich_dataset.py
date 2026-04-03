import json
import time
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")

RAW_FILE = 'data/raw/final_scraped_dataset.json'
ENRICHED_FILE = 'data/processed/enriched_dataset.json'

# Initialize the OpenAI client pointing to Fireworks AI
client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=FIREWORKS_API_KEY,
)

def draft_missing_description(specs_dict):
    """Uses Llama 3.1 8B on Fireworks to generate professional e-commerce copy."""
    prompt = f"""
    You are an e-commerce expert. Turn these raw specifications into a well-written, 
    4-sentence product description focusing on the practical performance traits and 
    advantages for the buyer. Do not invent any technical features not listed here.
    
    Specs: {json.dumps(specs_dict)}
    """
    
    response = client.chat.completions.create(
        model="accounts/fireworks/models/mixtral-8x22b-instruct", # The MoE Upgrade!
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3, 
        max_tokens=150
    )
    return response.choices[0].message.content.strip()

def generate_vector(text_chunk):
    """Generates a 768-dimension embedding array using Nomic."""
    response = client.embeddings.create(
        model="nomic-ai/nomic-embed-text-v1.5",
        input=text_chunk
    )
    return response.data[0].embedding

def run_enrichment():
    print("Loading Raw Scraped Dataset...")
    with open(RAW_FILE, 'r', encoding='utf-8') as f:
        raw_dataset = json.load(f)
        
    enriched_dataset = []
    processed_urls = set()
    
    # --- RESUMABILITY LOGIC ---
    os.makedirs(os.path.dirname(ENRICHED_FILE), exist_ok=True)
    
    if os.path.exists(ENRICHED_FILE):
        print("Found existing enriched dataset. Loading to resume progress...")
        with open(ENRICHED_FILE, 'r', encoding='utf-8') as f:
            try:
                enriched_dataset = json.load(f)
                processed_urls = {item['url'] for item in enriched_dataset}
                print(f"Resuming from item {len(processed_urls)}...")
            except json.JSONDecodeError:
                print("Error reading existing file. Starting fresh.")
    
    new_items_this_run = 0
    
    for index, item in enumerate(raw_dataset):
        if item['url'] in processed_urls:
            continue
            
        print(f"\nProcessing {index+1}/{len(raw_dataset)}: {item['title']}")
        
        final_desc = item.get('description', '')
        word_count = len(final_desc.split())
        has_specs = bool(item.get('specifications'))
        
        # 1. The Triage
        if word_count < 50 and has_specs:
            print(f"  -> Weak Description ({word_count} words). Llama 3.1 is drafting copy...")
            try:
                final_desc = draft_missing_description(item['specifications'])
                item['description'] = final_desc
            except Exception as e:
                print(f"  [!] Failed to generate description: {e}")
                continue
                
        elif word_count < 50 and not has_specs:
            print(f"  -> Ghost Item Detected. Skipping for now.")
            continue 
                
        # 2. The Vector
        embed_text = f"Title: {item['title']}\nDescription: {final_desc}\nSpecs: {json.dumps(item.get('specifications', {}))}"
        
        print("  -> Generating 768-Dimension Vector Mapping...")
        try:
            vector = generate_vector(embed_text)
            item['embedding'] = vector
        except Exception as e:
            print(f"  [!] Failed to generate embedding: {e}")
            continue
            
        # 3. Save and Backup
        enriched_dataset.append(item)
        processed_urls.add(item['url'])
        new_items_this_run += 1
        
        if new_items_this_run % 10 == 0:
            print("  -> Saving progress to JSON...")
            with open(ENRICHED_FILE, 'w', encoding='utf-8') as f:
                json.dump(enriched_dataset, f, indent=4)
                
        # Small sleep to be polite to the API, though Fireworks rate limits are generally generous
        time.sleep(0.5) 

    # Final Save
    with open(ENRICHED_FILE, 'w', encoding='utf-8') as f:
        json.dump(enriched_dataset, f, indent=4)
        
    print(f"\n✅ Enrichment Complete! Enriched dataset contains {len(enriched_dataset)} products.")

if __name__ == "__main__":
    run_enrichment()