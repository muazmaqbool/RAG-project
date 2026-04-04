import requests
from bs4 import BeautifulSoup
import json

def scrape_product_page(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() 
    except requests.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # 1. Core Elements
    title_element = soup.select_one('h1.product_title')
    price_element = soup.select_one('p.price bdi')
    image_element = soup.select_one('img#wpg-main-img')

    # 2. Enhanced Description Extraction
    # Fallback to standard WooCommerce containers if the main one fails
    desc_element = soup.select_one('div.product-description') or soup.select_one('#tab-description') or soup.select_one('.woocommerce-product-details__short-description')
    
    # Using separator="\n" prevents tabular text from mashing together into an unreadable string
    raw_description = desc_element.get_text(separator="\n", strip=True) if desc_element else "Not Found"

    # 3. Enhanced Specification (Tabular Data) Extraction
    specs = {}
    
    # Strategy A: Your original specific selector
    spec_rows = soup.select('tr.sts-attr-row')
    for row in spec_rows:
        key_elem = row.select_one('th')
        val_elem = row.select_one('td.value')
        if key_elem and val_elem:
            specs[key_elem.text.strip()] = val_elem.text.strip()

    # Strategy B: The Generic Table Hunter
    # Looks for tables inside descriptions or standard Woo spec tables
    additional_tables = soup.select('table.woocommerce-product-attributes, div.product-description table, #tab-description table')
    
    for table in additional_tables:
        for row in table.find_all('tr'):
            # Check for standard Header/Data pairs
            th = row.find('th')
            td = row.find('td')
            
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(separator=" ", strip=True)
                if key and key not in specs: # Don't overwrite Strategy A if it already worked
                    specs[key] = val
            else:
                # Fallback: Sometimes tables are just built with two standard columns (td and td)
                tds = row.find_all('td')
                if len(tds) == 2:
                    key = tds[0].get_text(strip=True)
                    val = tds[1].get_text(separator=" ", strip=True)
                    if key and key not in specs:
                        specs[key] = val

    # 4. Compiling the final JSON payload
    product_data = {
        "url": url,
        "title": title_element.text.strip() if title_element else "Not Found",
        "price_pkr": price_element.text.replace('₨', '').strip() if price_element else "Not Found",
        "description": raw_description,
        "image_url": image_element.get('src') if image_element else "Not Found",
        "specifications": specs
    }

    return product_data

# --- TEST IT HERE ---
# Find a URL from your audit that you KNOW has sparse specs but a tabular description on the live site
test_url = 'https://alaqsa.com.pk/product/hp-elitebook-840-g6-core-i7-8th-gen-16gb-256gb-ssd14-fhd-ips-led/'
result = scrape_product_page(test_url)

print(json.dumps(result, indent=4))