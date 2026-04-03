import requests
from bs4 import BeautifulSoup
import json
import time
import os

def scrape_product_data(url, category_paths):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Base schema for a 404/Unavailable product
    base_data = {
        "url": url,
        "title": "Unknown",
        "is_available": False,
        "pricing": {"amount_pkr": None, "is_call_for_price": False},
        "description": "",
        "categories": category_paths,
        "specifications": {}
    }

    try:
        # Increased timeout to 15 seconds to handle spotty internet
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 404:
            print(f"  [-] 404 Not Found (Marking Unavailable): {url}")
            return base_data
            
        response.raise_for_status()
        
    except requests.RequestException as e:
        # CRITICAL: If the internet drops, we return None. 
        # This ensures the item is NOT saved, so it will be retried next time.
        print(f"  [!] Connection Error for {url}: {e}")
        return None 

    soup = BeautifulSoup(response.content, 'html.parser')
    
    title_elem = soup.select_one('h1.product_title')
    price_elem = soup.select_one('p.price bdi')
    desc_elem = soup.select_one('div.product-description')
    
    specs = {}
    spec_rows = soup.select('tr.sts-attr-row')
    if spec_rows:
        for row in spec_rows:
            key_elem = row.select_one('th')
            val_elem = row.select_one('td.value')
            if key_elem and val_elem:
                specs[key_elem.text.strip()] = val_elem.text.strip()

    price_text = price_elem.text.lower() if price_elem else ""
    pricing_data = {"amount_pkr": None, "is_call_for_price": False}
    
    if "call" in price_text or not price_text:
        pricing_data["is_call_for_price"] = True
    else:
        cleaned_price = "".join(filter(str.isdigit, price_text))
        if cleaned_price:
            int_price = int(cleaned_price)
            if int_price == 0:
                pricing_data["is_call_for_price"] = True
            else:
                pricing_data["amount_pkr"] = int_price
        else:
            pricing_data["is_call_for_price"] = True

    product_data = {
        "url": url,
        "title": title_elem.text.strip() if title_elem else "Unknown",
        "is_available": True,
        "pricing": pricing_data,
        "description": desc_elem.text.strip() if desc_elem else "",
        "categories": category_paths,
        "specifications": specs
    }

    return product_data

if __name__ == "__main__":
    input_file = '../data/raw/master_product_urls.json'
    output_file = '../data/raw/final_scraped_dataset.json'
    
    print("Loading Master URLs...")
    with open(input_file, 'r', encoding='utf-8') as f:
        url_dict = json.load(f)
        
    total_urls = len(url_dict)
    final_dataset = []
    scraped_urls = set()
    
    # --- RESUMABILITY LOGIC ---
    if os.path.exists(output_file):
        print("Found existing dataset. Loading to resume progress...")
        with open(output_file, 'r', encoding='utf-8') as f:
            try:
                final_dataset = json.load(f)
                # Create a fast-lookup set of URLs we already successfully processed
                scraped_urls = {item['url'] for item in final_dataset}
                print(f"Resuming from item {len(scraped_urls)}...")
            except json.JSONDecodeError:
                print("Error reading existing file. Starting fresh.")
    
    count = 0
    new_items_this_run = 0
    
    for url, categories in url_dict.items():
        count += 1
        
        # Skip if we already scraped it in a previous run
        if url in scraped_urls:
            continue
            
        print(f"Scraping {count}/{total_urls}: {url}")
        
        data = scrape_product_data(url, categories)
        
        # If data is None, an internet error occurred. We skip saving so it retries later.
        if data:
            final_dataset.append(data)
            scraped_urls.add(url)
            new_items_this_run += 1
            
            # Save progress frequently (every 10 successful items) to protect against drops
            if new_items_this_run % 10 == 0:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(final_dataset, f, indent=4)
                print(f"  --> Progress saved ({len(final_dataset)} total items)")
                
        time.sleep(0.5) 

    # Final Save when the loop finishes
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_dataset, f, indent=4)
        
    print(f"\nScraping complete! Dataset contains {len(final_dataset)} products.")