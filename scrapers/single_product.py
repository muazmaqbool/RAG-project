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
    
    # 1. Exact Selectors based on the Alaqsa HTML structure
    title_element = soup.select_one('h1.product_title')
    price_element = soup.select_one('p.price bdi')
    desc_element = soup.select_one('div.product-description')
    image_element = soup.select_one('img#wpg-main-img')

    # 2. Extracting the structured specifications table
    specs = {}
    spec_rows = soup.select('tr.sts-attr-row')
    for row in spec_rows:
        key_elem = row.select_one('th')
        val_elem = row.select_one('td.value')
        if key_elem and val_elem:
            # We use .text.strip() to clean off any HTML tags and whitespace
            specs[key_elem.text.strip()] = val_elem.text.strip()

    # 3. Compiling the final JSON payload
    product_data = {
        "url": url,
        "title": title_element.text.strip() if title_element else "Not Found",
        # We replace the currency symbol to leave just the clean integer for easier processing later
        "price_pkr": price_element.text.replace('₨', '').strip() if price_element else "Not Found",
        "description": desc_element.text.strip() if desc_element else "Not Found",
        "image_url": image_element.get('src') if image_element else "Not Found",
        "specifications": specs
    }

    return product_data

# --- TEST IT HERE ---
test_url = 'https://alaqsa.com.pk/product/dell-latitude-5540-core-i5-13th-gen-8gb-ddr5-512gb-nvme-ssd-15-6-fhd-ips-led-windows-11pro/'
result = scrape_product_page(test_url)

print(json.dumps(result, indent=4))