import requests
from bs4 import BeautifulSoup
import json
import time

def extract_product_links_from_page(url):
    """Extracts product URLs from a single page, identical to our bulletproof crawler."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            return None # Reached the end of the pagination
        response.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    product_urls = []
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if '/product/' in href and '/product-category/' not in href:
            product_urls.append(href)
            
    return list(set(product_urls))

def crawl_category_with_pagination(base_category_url, category_path, master_dict):
    """Crawls a category and all its subsequent pages (page/2/, page/3/, etc.)"""
    page_num = 1
    
    while True:
        # WooCommerce standard pagination structure
        current_url = base_category_url if page_num == 1 else f"{base_category_url}page/{page_num}/"
        print(f"  -> Scanning: {current_url}")
        
        links = extract_product_links_from_page(current_url)
        
        # If we get None (404 error) or an empty list, we've hit the last page
        if not links:
            break
            
        for link in links:
            if link not in master_dict:
                master_dict[link] = []
            
            # Format the category path as a string (e.g., "New Laptops > Dell")
            path_string = " > ".join(category_path)
            if path_string not in master_dict[link]:
                master_dict[link].append(path_string)
                
        page_num += 1
        time.sleep(0.5) # BE POLITE: 0.5s delay so we don't crash your father's website!

def process_taxonomy_node(node, current_path, master_dict):
    """Recursively traverses the JSON tree."""
    category_name = node.get('name')
    category_url = node.get('url')
    
    new_path = current_path + [category_name]
    
    # If it's a valid link, crawl it
    if category_url and category_url != '#':
        print(f"\nCrawling Category: {' > '.join(new_path)}")
        crawl_category_with_pagination(category_url, new_path, master_dict)
        
    # If it has subcategories, dig deeper
    subcategories = node.get('subcategories', [])
    for sub_node in subcategories:
        process_taxonomy_node(sub_node, new_path, master_dict)

# --- EXECUTION ---
if __name__ == "__main__":
    print("Loading taxonomy...")
    with open('../data/raw/category_taxonomy.json', 'r', encoding='utf-8') as f:
        taxonomy = json.load(f)
        
    master_product_dict = {}
    
    print("Initiating Master Crawl (This may take a few minutes...)")
    for main_category in taxonomy:
        process_taxonomy_node(main_category, [], master_product_dict)
        
    # Save the final mapping
    output_file = '../data/raw/master_product_urls.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(master_product_dict, f, indent=4)
        
    print(f"\nDone! Found {len(master_product_dict)} unique products.")
    print(f"Data saved to {output_file}")