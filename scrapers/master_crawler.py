import requests
from bs4 import BeautifulSoup
import json
import time
import os

def scrape_product_data(url, category_paths):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Base schema matching what daily_update.py expects
    base_data = {
        "url": url,
        "title": "Unknown",
        "is_available": False,
        "price": None, # Flattened to match daily_update.py
        "description": "",
        "categories": category_paths,
        "specifications": {}
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 404:
            print(f"  [-] 404 Not Found (Marking Unavailable): {url}")
            return base_data
            
        response.raise_for_status()
        
    except requests.RequestException as e:
        # CRITICAL FIX: Return the base_data instead of None so the orchestrator knows it failed
        print(f"  [!] Connection Error for {url} (Marking Unavailable): {e}")
        return base_data 

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # --- 1. Core Elements ---
    title_elem = soup.select_one('h1.product_title')
    price_elem = soup.select_one('p.price bdi')
    image_elem = soup.select_one('img#wpg-main-img')
    
    # --- 2. Enhanced Description Extraction ---
    desc_elem = soup.select_one('div.product-description') or soup.select_one('#tab-description') or soup.select_one('.woocommerce-product-details__short-description')
    raw_description = desc_elem.get_text(separator="\n", strip=True) if desc_elem else ""

    # --- 3. Enhanced Specification (Tabular Data) Extraction ---
    specs = {}
    
    spec_rows = soup.select('tr.sts-attr-row')
    if spec_rows:
        for row in spec_rows:
            key_elem = row.select_one('th')
            val_elem = row.select_one('td.value')
            if key_elem and val_elem:
                specs[key_elem.text.strip()] = val_elem.text.strip()

    additional_tables = soup.select('table.woocommerce-product-attributes, div.product-description table, #tab-description table')
    for table in additional_tables:
        for row in table.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(separator=" ", strip=True)
                if key and key not in specs:
                    specs[key] = val
            else:
                tds = row.find_all('td')
                if len(tds) == 2:
                    key = tds[0].get_text(strip=True)
                    val = tds[1].get_text(separator=" ", strip=True)
                    if key and key not in specs:
                        specs[key] = val

    # --- 4. Price Parsing (Flattened Schema) ---
    price_text = price_elem.text.lower() if price_elem else ""
    final_price = None
    is_call = False # <--- NEW: Explicitly track the flag
    
    if "call" in price_text or not price_text:
        is_call = True
    else:
        cleaned_price = "".join(filter(str.isdigit, price_text))
        if cleaned_price and int(cleaned_price) > 0:
            final_price = int(cleaned_price)
        else:
            is_call = True

    # --- 5. Final Assembly ---
    product_data = {
        "url": url,
        "title": title_elem.text.strip() if title_elem else "Unknown",
        "is_available": True,
        "price": final_price,
        "is_call_for_price": is_call, # <--- NEW: Save it to the raw JSON
        "description": raw_description,
        "categories": category_paths,
        "specifications": specs,
        "image_url": image_elem.get('src') if image_elem else None
    }

    return product_data

def run_web_scraper():
    input_file = 'data/raw/master_product_urls.json'
    output_file = 'data/raw/todays_scrape.json' 
    
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
                scraped_urls = {item['url'] for item in final_dataset}
                print(f"Resuming from item {len(scraped_urls)}...")
            except json.JSONDecodeError:
                print("Error reading existing file. Starting fresh.")
    
    count = 0
    new_items_this_run = 0
    
    for url, categories in url_dict.items():
        count += 1
        
        if url in scraped_urls:
            continue
            
        print(f"Scraping {count}/{total_urls}: {url}")
        
        data = scrape_product_data(url, categories)
        
        # We always append data now, even if it's the base "Unavailable" schema
        final_dataset.append(data)
        scraped_urls.add(url)
        new_items_this_run += 1
        
        if new_items_this_run % 10 == 0:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(final_dataset, f, indent=4)
                
            print(f"\nProgress Saved! Dataset contains {len(final_dataset)} products.")
            
        time.sleep(0.5) 

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_dataset, f, indent=4)
        
    print(f"\nScraping complete! Dataset contains {len(final_dataset)} products.")
    
if __name__ == "__main__":
    run_web_scraper()