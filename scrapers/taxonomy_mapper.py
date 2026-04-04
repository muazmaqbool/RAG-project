import requests
from bs4 import BeautifulSoup
import json

def map_website_taxonomy(base_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching the homepage: {e}")
        return {}

    soup = BeautifulSoup(response.content, 'html.parser')
    main_menu = soup.find('ul', id='mega-menu-primary')

    # This is our recursive extraction function
    def extract_menu_nodes(ul_element):
        nodes = []
        if not ul_element:
            return nodes
            
        # recursive=False ensures we only get the direct children (the immediate next level)
        for li in ul_element.find_all('li', class_='mega-menu-item', recursive=False):
            a_tag = li.find('a', class_='mega-menu-link', recursive=False)
            
            if not a_tag:
                continue
                
            name = a_tag.text.strip()
            url = a_tag.get('href')
            
            node_data = {
                "name": name,
                "url": url
            }
            
            # Check if this menu item has a dropdown (sub-menu)
            sub_ul = li.find('ul', class_='mega-sub-menu', recursive=False)
            if sub_ul:
                # If it does, call this exact same function again to dig deeper
                node_data["subcategories"] = extract_menu_nodes(sub_ul)
                
            nodes.append(node_data)
            
        return nodes

    raw_taxonomy = extract_menu_nodes(main_menu)
    
    # Optional Clean-up: Filter out non-product pages like "Home" or "Contact Us"
    # We only keep branches that contain "product-category" or "brand" somewhere in their URLs
    def filter_taxonomy(nodes):
        filtered = []
        for node in nodes:
            keep_node = False
            # If the current node is a valid category
            if '/product-category/' in node['url'] or '/brand/' in node['url']:
                keep_node = True
            
            # Or if any of its subcategories are valid categories
            if 'subcategories' in node:
                node['subcategories'] = filter_taxonomy(node['subcategories'])
                if len(node['subcategories']) > 0:
                    keep_node = True
                    
            if keep_node:
                filtered.append(node)
        return filtered

    clean_taxonomy = filter_taxonomy(raw_taxonomy)
    return clean_taxonomy

# --- TEST IT HERE ---
homepage_url = 'https://alaqsa.com.pk/'
taxonomy_tree = map_website_taxonomy(homepage_url)

# Let's save this directly to our raw data folder so we don't have to scrape it again!
output_file = 'data/raw/category_taxonomy.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(taxonomy_tree, f, indent=4)

print(f"Taxonomy successfully mapped and saved to {output_file}")
print(json.dumps(taxonomy_tree, indent=4))