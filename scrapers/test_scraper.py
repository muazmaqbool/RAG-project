import requests
from bs4 import BeautifulSoup
import json

def test_scrape_product(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"error": f"Status code {response.status_code}"}
    except requests.RequestException as e:
        return {"error": str(e)}

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # 1. Core Elements
    title_elem = soup.select_one('h1.product_title')
    price_elem = soup.select_one('p.price bdi')
    desc_elem = soup.select_one('div.product-description')
    image_elem = soup.select_one('img#wpg-main-img')

    # 2. Extract Specifications Table
    specs = {}
    spec_rows = soup.select('tr.sts-attr-row')
    if spec_rows:
        for row in spec_rows:
            key_elem = row.select_one('th')
            val_elem = row.select_one('td.value')
            if key_elem and val_elem:
                specs[key_elem.text.strip()] = val_elem.text.strip()

    # 3. Compile Data
    product_data = {
        "url": url,
        "title": title_elem.text.strip() if title_elem else "MISSING",
        "price_pkr": price_elem.text.replace('₨', '').replace(',', '').strip() if price_elem else "MISSING",
        "description": desc_elem.text.strip() if desc_elem else "MISSING",
        "image_url": image_elem.get('src') if image_elem else "MISSING",
        "specifications": specs
    }

    return product_data

# --- OUR DIVERSE TEST BATCH ---
test_urls = [
    # A standard accessory (Card Reader)
    "https://alaqsa.com.pk/product/onten-8107-usb3-0-to-cf-tf-sd-card-reader-with-usb3-02-ports/",
    # A gaming accessory
    "https://alaqsa.com.pk/product/onikuma-k19-professional-gaming-headphone/",
    # A smart gadget
    "https://alaqsa.com.pk/product/m8-64gb-hdmi-game-stick-lite-console/"
]

print("Starting Sandbox Test...\n" + "="*40)

for url in test_urls:
    print(f"\nScraping: {url}")
    result = test_scrape_product(url)
    # Print the result beautifully formatted
    print(json.dumps(result, indent=4))
    print("-" * 40)