import requests
from bs4 import BeautifulSoup
import json

def get_product_urls(category_url):
    # Added a few more headers to mimic a real browser even better
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    try:
        response = requests.get(category_url, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching the category URL: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    
    product_urls = []
    
    # Foolproof Approach: Find ALL links on the page
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        
        # Keep it only if it's a direct product page 
        # (and exclude category links just in case)
        if '/product/' in href and '/product-category/' not in href:
            product_urls.append(href)
            
    # set() removes duplicates because grid images and titles often link to the same place
    return list(set(product_urls)) 

# --- TEST IT HERE ---
test_category_url = 'https://alaqsa.com.pk/product-category/new-laptops-price-pakistan/hp/'
urls = get_product_urls(test_category_url)

print(f"Successfully extracted {len(urls)} unique product URLs:")
print(json.dumps(urls, indent=4))