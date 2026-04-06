import json
import time
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin

OUTPUT_FILE = 'data/raw/master_product_urls.json'
HOMEPAGE_URL = 'https://alaqsa.com.pk/'

# --- STEP 1: MAP THE TAXONOMY (From old taxonomy_mapper.py) ---
def map_website_taxonomy(base_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching the homepage: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    main_menu = soup.find('ul', id='mega-menu-primary')

    def extract_menu_nodes(ul_element):
        nodes = []
        if not ul_element: return nodes
            
        for li in ul_element.find_all('li', class_='mega-menu-item', recursive=False):
            a_tag = li.find('a', class_='mega-menu-link', recursive=False)
            if not a_tag: continue
                
            node_data = {
                "name": a_tag.text.strip(),
                "url": a_tag.get('href')
            }
            
            sub_ul = li.find('ul', class_='mega-sub-menu', recursive=False)
            if sub_ul:
                node_data["subcategories"] = extract_menu_nodes(sub_ul)
                
            nodes.append(node_data)
        return nodes

    def filter_taxonomy(nodes):
        filtered = []
        for node in nodes:
            keep_node = False
            if '/product-category/' in node['url'] or '/brand/' in node['url']:
                keep_node = True
            
            if 'subcategories' in node:
                node['subcategories'] = filter_taxonomy(node['subcategories'])
                if len(node['subcategories']) > 0:
                    keep_node = True
                    
            if keep_node: filtered.append(node)
        return filtered

    raw_taxonomy = extract_menu_nodes(main_menu)
    return filter_taxonomy(raw_taxonomy)

def flatten_taxonomy(nodes, current_path=""):
    """Recursively digs through the taxonomy tree to find all category URLs."""
    category_map = {}
    for node in nodes:
        name = node['name']
        url = node.get('url')
        path = f"{current_path} > {name}" if current_path else name
        
        if url and ('/product-category/' in url or '/brand/' in url):
            category_map[url] = path
            
        if 'subcategories' in node:
            category_map.update(flatten_taxonomy(node['subcategories'], path))
            
    return category_map

# --- STEP 2: SCRAPE THE URLs (From old build_master_urls.py) ---
def get_product_urls(base_category_url):
    """Hits a category page, handles pagination, and grabs all absolute product links."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    all_category_urls = set()
    page = 1
    
    while True:
        current_url = base_category_url if page == 1 else f"{base_category_url.rstrip('/')}/page/{page}/"
        try:
            response = requests.get(current_url, headers=headers, timeout=15)
            if response.status_code == 404: break
            response.raise_for_status()
        except requests.exceptions.RequestException:
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        products_found = 0
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if '/product/' in href and '/product-category/' not in href:
                absolute_url = urljoin(current_url, href)
                if absolute_url not in all_category_urls:
                    all_category_urls.add(absolute_url)
                    products_found += 1
        
        if products_found == 0: break
        print(f"    - Page {page}: Found {products_found} products.")
        page += 1
        time.sleep(1)

    return list(all_category_urls)

# --- MASTER CONTROLLER ---
def build_master_list():
    print("🗺️ Mapping live website taxonomy...")
    taxonomy_tree = map_website_taxonomy(HOMEPAGE_URL)
    
    print("📂 Flattening taxonomy tree...")
    category_map = flatten_taxonomy(taxonomy_tree)
    print(f"Found {len(category_map)} distinct category pages to crawl.")

    master_urls = {}
    
    for index, (cat_url, cat_path) in enumerate(category_map.items()):
        print(f"\n[{index+1}/{len(category_map)}] Crawling Category: {cat_path}")
        product_links = get_product_urls(cat_url)
        print(f"  -> Total in category: {len(product_links)} products.")
        
        for link in product_links:
            if link not in master_urls:
                master_urls[link] = []
            if cat_path not in master_urls[link]:
                master_urls[link].append(cat_path)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(master_urls, f, indent=4)
        
    print(f"\n✅ Master URL list built! Found {len(master_urls)} unique products.")

if __name__ == "__main__":
    build_master_list()