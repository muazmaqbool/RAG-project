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
    
    title_elem = soup.select_one('h1.product_title')
    price_elem = soup.select_one('p.price bdi')
    
    # --- UPDATED PRICE PARSING LOGIC ---
    price_text = price_elem.text.lower() if price_elem else ""
    pricing_data = {"amount_pkr": None, "is_call_for_price": False}
    
    if "call" in price_text or not price_text:
        pricing_data["is_call_for_price"] = True
    else:
        # Extract only the digits
        cleaned_price = "".join(filter(str.isdigit, price_text))
        
        if cleaned_price:
            int_price = int(cleaned_price)
            # NEW: If the integer is 0, it is a placeholder for 'Call for Price'
            if int_price == 0:
                pricing_data["is_call_for_price"] = True
                pricing_data["amount_pkr"] = None
            else:
                pricing_data["amount_pkr"] = int_price
                pricing_data["is_call_for_price"] = False
        else:
            pricing_data["is_call_for_price"] = True
    # -----------------------------------

    product_data = {
        "url": url,
        "title": title_elem.text.strip() if title_elem else "Unknown",
        "pricing": pricing_data
    }

    return product_data

# Test it
test_url = "https://alaqsa.com.pk/product/acer-3820-battery/"
print(json.dumps(test_scrape_product(test_url), indent=4))