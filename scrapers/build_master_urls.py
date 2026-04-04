import json
import time
import requests
from bs4 import BeautifulSoup
import os

TAXONOMY_FILE = 'data/raw/category_taxonomy.json'
OUTPUT_FILE = 'data/raw/master_product_urls.json'

def get_product_urls(category_url):
    """Hits a single category page and grabs all product links."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    }
    try:
        response = requests.get(category_url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"  [!] Error fetching {category_url}: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    urls = []
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if '/product/' in href and '/product-category/' not in href:
            urls.append(href)
    return list(set(urls))

def flatten_taxonomy(nodes, current_path=""):
    """Recursively digs through the taxonomy tree to find all category URLs."""
    category_map = {}
    for node in nodes:
        name = node['name']
        url = node.get('url')
        
        # Build the breadcrumb path (e.g., "Laptops > HP")
        path = f"{current_path} > {name}" if current_path else name
        
        # Only grab pages that are actual catalogs
        if url and ('/product-category/' in url or '/brand/' in url):
            category_map[url] = path
            
        if 'subcategories' in node:
            category_map.update(flatten_taxonomy(node['subcategories'], path))
            
    return category_map

def build_master_list():
    if not os.path.exists(TAXONOMY_FILE):
        print("❌ Run taxonomy_mapper.py first!")
        return

    with open(TAXONOMY_FILE, 'r', encoding='utf-8') as f:
        taxonomy_tree = json.load(f)

    print("🗺️  Flattening taxonomy tree...")
    category_map = flatten_taxonomy(taxonomy_tree)
    print(f"Found {len(category_map)} distinct category pages to crawl.")

    master_urls = {}
    
    # Loop through every category page and grab the products
    for index, (cat_url, cat_path) in enumerate(category_map.items()):
        print(f"[{index+1}/{len(category_map)}] Crawling: {cat_path}")
        
        product_links = get_product_urls(cat_url)
        print(f"  -> Found {len(product_links)} products.")
        
        for link in product_links:
            # If we've seen this product before, just append the new category path to its list
            if link not in master_urls:
                master_urls[link] = []
            if cat_path not in master_urls[link]:
                master_urls[link].append(cat_path)
                
        time.sleep(1) # Be polite to their server

    # Save the final massive dictionary
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(master_urls, f, indent=4)
        
    print(f"\n✅ Master URL list built! Found {len(master_urls)} unique products.")

if __name__ == "__main__":
    build_master_list()