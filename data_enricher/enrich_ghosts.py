import json
import time
import os
from openai import OpenAI
from duckduckgo_search import DDGS
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")

RAW_FILE = 'data/raw/final_scraped_dataset.json'
ENRICHED_FILE = 'data/processed/enriched_dataset.json'

client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=FIREWORKS_API_KEY,
)

def search_web_for_product(product_title, brand):
    """Uses DuckDuckGo to grab the top 3 search snippets for context."""
    query = f"{brand} {product_title} specifications features"
    try:
        results = DDGS().text(query, max_results=3)
        context = "\n".join([f"- {res['body']}" for res in results])
        return context if context else "No web results found."
    except Exception as e:
        print(f"  [!] Search error: {e}")
        return "No web results found."

def hunt_ghost_data(product_title, search_context):
    """Uses Mixtral to extract specs and write an SEO-optimized description based on web context."""
    prompt = f"""
    You are an e-commerce data engineer and expert SEO copywriter specializing in tech accessories and peripherals.
    Product Title: "{product_title}"
    
    Web Search Context:
    {search_context}
    
    Based ONLY on the context provided above, deduce what this product is.
    Return EXACTLY a JSON object with two keys:
    1. "description": A 4-sentence professional description of its features.
    2. "specifications": A dictionary of 3 to 5 key technical specifications (e.g., {{"Interface": "USB 3.0"}}).
    
    FATAL RULES FOR DESCRIPTION:
    You MUST analyze the context and explicitly categorize the product by naturally weaving in at least 3 of these strategic keywords into your description to help our search engine:
    - Quality/Form Factor Tiers: [Value, Standard, Premium, Heavy-Duty, Compact, Portable, High-Capacity]
    - Use-Cases: [Travel/On-the-Go, Home Office, Mobile Devices, Desk Setup, Gaming, Everyday Charging, Professional]
    
    If the context is insufficient to determine what the product is, return {{"description": "Not found", "specifications": {{}}}}.
    """
    
    response = client.chat.completions.create(
        model="accounts/fireworks/models/mixtral-8x22b-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1, 
        response_format={"type": "json_object"} 
    )
    
    return json.loads(response.choices[0].message.content.strip())

def generate_vector(text_chunk):
    """Generates a 768-dimension embedding array using Nomic."""
    response = client.embeddings.create(
        model="nomic-ai/nomic-embed-text-v1.5",
        input=text_chunk
    )
    return response.data[0].embedding

def run_ghost_hunter():
    print("Loading Datasets...")
    with open(RAW_FILE, 'r', encoding='utf-8') as f:
        raw_dataset = json.load(f)
        
    enriched_dataset = []
    processed_urls = set()
    
    # Load existing enriched data so we don't overwrite the work from the first script
    if os.path.exists(ENRICHED_FILE):
        with open(ENRICHED_FILE, 'r', encoding='utf-8') as f:
            try:
                enriched_dataset = json.load(f)
                processed_urls = {item['url'] for item in enriched_dataset}
            except json.JSONDecodeError:
                pass
                
    new_items_this_run = 0
    
    for index, item in enumerate(raw_dataset):
        # We ONLY want to process items that the first script skipped
        if item['url'] in processed_urls:
            continue
            
        final_desc = item.get('description', '')
        word_count = len(final_desc.split())
        has_specs = bool(item.get('specifications'))
        
        # Identify the Ghosts
        if word_count < 50 and not has_specs:
            print(f"\n👻 Hunting Ghost {index+1}/{len(raw_dataset)}: {item['title']}")
            
            categories = item.get('categories', [])
            brand = ""
            for cat in categories:
                if "Brands >" in cat:
                    brand = cat.split(">")[-1].strip()
            
            # 1. Search the Web
            print("  -> Searching DuckDuckGo...")
            search_context = search_web_for_product(item['title'], brand)
            
            # 2. Extract and Generate via Mixtral
            print("  -> Mixtral is analyzing search context...")
            try:
                hunted_data = hunt_ghost_data(item['title'], search_context)
                
                if hunted_data['description'].lower() == "not found":
                    print("  [!] Product too obscure. Leaving as ghost.")
                    # We add it anyway so we don't keep retrying it in the future
                    enriched_dataset.append(item)
                    processed_urls.add(item['url'])
                    continue
                    
                print("  -> Successfully structured web data!")
                item['description'] = hunted_data['description']
                item['specifications'] = hunted_data['specifications']
                
            except Exception as e:
                print(f"  [!] Mixtral extraction failed: {e}")
                continue
                
            # 3. Generate the Vector
            embed_text = f"Title: {item['title']}\nDescription: {item['description']}\nSpecs: {json.dumps(item['specifications'])}"
            print("  -> Generating 768-Dimension Vector Mapping...")
            try:
                vector = generate_vector(embed_text)
                item['embedding'] = vector
            except Exception as e:
                print(f"  [!] Failed to generate embedding: {e}")
                continue
                
            # 4. Save and Backup
            enriched_dataset.append(item)
            processed_urls.add(item['url'])
            new_items_this_run += 1
            
            if new_items_this_run % 5 == 0: # Save more frequently since searching is slower
                print("  -> Saving progress to JSON...")
                with open(ENRICHED_FILE, 'w', encoding='utf-8') as f:
                    json.dump(enriched_dataset, f, indent=4)
                    
            # DuckDuckGo will block you if you search too fast. A 3-second sleep is required.
            time.sleep(3) 

    # Final Save
    with open(ENRICHED_FILE, 'w', encoding='utf-8') as f:
        json.dump(enriched_dataset, f, indent=4)
        
    print("\n✅ Ghost Hunting Complete! Dataset is now fully enriched.")

if __name__ == "__main__":
    run_ghost_hunter()