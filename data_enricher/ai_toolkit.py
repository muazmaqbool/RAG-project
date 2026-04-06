import os
import json
import time
from openai import OpenAI
from duckduckgo_search import DDGS
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=os.getenv("FIREWORKS_API_KEY"),
)

# ==========================================
# CORE UTILITIES
# ==========================================

def extract_json_from_text(raw_text):
    try:
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            return json.loads(raw_text[start_idx:end_idx + 1])
    except Exception as e:
        print(f"      ⚠️ JSON Parse Error in AI Toolkit: {e}")
    return {}

def generate_vector(text_chunk, max_retries=3):
    """Centralized vector generator with auto-retry."""
    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model="nomic-ai/nomic-embed-text-v1.5",
                input=text_chunk
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"      ⚠️ Embedding API Error (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return None
            time.sleep(2 ** attempt) # Waits 1s, then 2s, then gives up

# ==========================================
# TOOL 1: THE COPYWRITER
# ==========================================

def draft_missing_description(specs_dict, title, max_retries=3):
    prompt = f"""
    You are an expert e-commerce SEO copywriter. 
    Product Title: {title}
    Specs: {json.dumps(specs_dict)}
    Write a well-crafted, 4-sentence product description.
    FATAL RULES:
    1. Do NOT invent any technical features not explicitly listed in the specs.
    2. Weave in at least 3 intent keywords (e.g., Budget, Premium, Gaming, Office, Portable).
    """
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="accounts/fireworks/models/mixtral-8x22b-instruct", 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3, 
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"      ⚠️ Copywriter API Error (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return ""
            time.sleep(2 ** attempt)

# ==========================================
# TOOL 2: THE GHOST HUNTER
# ==========================================

def search_web_for_product(product_title, brand, max_retries=3):
    query = f"{brand} {product_title} specifications features"
    for attempt in range(max_retries):
        try:
            results = DDGS().text(query, max_results=3)
            context = "\n".join([f"- {res['body']}" for res in results])
            return context if context else "No web results found."
        except Exception as e:
            print(f"      ⚠️ DuckDuckGo Error (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return "No web results found."
            time.sleep(2 ** attempt)

def hunt_ghost_data(product_title, search_context, max_retries=3):
    prompt = f"""
    Product Title: "{product_title}"
    Web Search Context: {search_context}
    Deduce what this product is based ONLY on the context.
    Return EXACTLY a JSON object:
    {{
        "description": "4-sentence professional description...",
        "specifications": {{"Interface": "USB 3.0", "Color": "Black"}}
    }}
    If the context is insufficient, return {{"description": "Not found", "specifications": {{}}}}.
    """
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="accounts/fireworks/models/mixtral-8x22b-instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            return extract_json_from_text(response.choices[0].message.content)
        except Exception as e:
            print(f"      ⚠️ Ghost Hunter API Error (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return {"description": "Not found", "specifications": {}}
            time.sleep(2 ** attempt)

# ==========================================
# TOOL 3: THE SCHEMA ROUTER
# ==========================================

def determine_schema(category_path, schemas_dict):
    cat_lower = str(category_path).lower()
    if "laptop stand" in cat_lower or "cooling pad" in cat_lower: return schemas_dict.get("Laptop Stands & Cooling Pads", {})
    if "laptop" in cat_lower: return schemas_dict.get("Laptops", {})
    if "power bank" in cat_lower: return schemas_dict.get("Power Banks", {})
    if "watch" in cat_lower or "band" in cat_lower: return schemas_dict.get("Smartwatches", {}) 
    if "charger" in cat_lower or "adapter" in cat_lower: return schemas_dict.get("Chargers", {})
    if "data cable" in cat_lower: return schemas_dict.get("Data Cables", {})
    if "multifunction" in cat_lower or "hub" in cat_lower: return schemas_dict.get("Multifunction Adapters", {})
    if "convertor" in cat_lower: return schemas_dict.get("Convertors", {})
    if "bluetooth handsfree" in cat_lower: return schemas_dict.get("Bluetooth Handsfree", {})
    if "stereo handsfree" in cat_lower: return schemas_dict.get("Stereo Handsfree", {})
    if "ring light" in cat_lower: return schemas_dict.get("Ring Lights", {})
    if "gaming" in cat_lower: return schemas_dict.get("Gaming Accessories", {})
    if "mix gadget" in cat_lower: return schemas_dict.get("Mix Gadgets", {})
    if "keyboard" in cat_lower or "mouse" in cat_lower: return schemas_dict.get("Keyboards and Mouse", {})
    if "speaker" in cat_lower or "headphone" in cat_lower: return schemas_dict.get("Speakers and Headphones", {})
    if "extension lead" in cat_lower or "smart switch" in cat_lower: return schemas_dict.get("Extension Leads & Smart Switches", {})
    if "mobile holder" in cat_lower: return schemas_dict.get("Mobile Holders", {})
    if "hub" in cat_lower or "dock" in cat_lower: return schemas_dict.get("Multifunction Hubs & Docks", {})
    if "usb card" in cat_lower or "usb device" in cat_lower: return schemas_dict.get("USB Cards & Devices", {})
    if "card reader" in cat_lower: return schemas_dict.get("Card Readers", {})
    if "android box" in cat_lower or "screen mirror" in cat_lower: return schemas_dict.get("Android BOX & Screen Mirror", {})
    if "recording" in cat_lower or "presenter" in cat_lower: return schemas_dict.get("Recording Accessories", {})
    if "usb hub" in cat_lower: return schemas_dict.get("USB Hubs", {})
    if "tripod" in cat_lower or "selfi" in cat_lower: return schemas_dict.get("Tripods & Selfie Sticks", {})
    if "network adapter" in cat_lower: return schemas_dict.get("Network Adapters & Accessories", {})
    if "projector" in cat_lower: return schemas_dict.get("Smart Projectors", {})
    if "enclosure" in cat_lower: return schemas_dict.get("External Enclosures", {})
    if "laptop bag" in cat_lower: return schemas_dict.get("Laptop Bags", {})
    if "ssd" in cat_lower: return schemas_dict.get("SSDs", {})
    if "software" in cat_lower: return schemas_dict.get("Softwares", {})
    if "graphic tablet" in cat_lower or "drawing tablet" in cat_lower: return schemas_dict.get("Graphic Tablets", {})
    if "gaming stick" in cat_lower: return schemas_dict.get("Gaming Sticks", {})
    if "camera" in cat_lower: return schemas_dict.get("Smart Cameras", {})
    if "batteries" in cat_lower or "battery" in cat_lower: return schemas_dict.get("Batteries", {})
    return schemas_dict.get("General", {})

# ==========================================
# TOOL 4: THE STRICT SPEC EXTRACTOR
# ==========================================

def extract_search_specs(title, description, raw_specs, target_schema, max_retries=3):
    prompt = f"""
    Product Title: {title}
    Description: {description}
    Raw Specs: {json.dumps(raw_specs)}
    TARGET STRICT SCHEMA:
    {json.dumps(target_schema, indent=2)}
    FATAL RULES:
    1. Extract strict, numeric/boolean data using ONLY the exact keys from the TARGET STRICT SCHEMA.
    2. Adhere strictly to the data types requested. 
    3. If a value isn't found in the text, use null. DO NOT hallucinate specs.
    Return EXACTLY a JSON object containing ONLY the keys found in the Strict Schema.
    """
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="accounts/fireworks/models/mixtral-8x22b-instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            return extract_json_from_text(response.choices[0].message.content)
        except Exception as e:
            print(f"      ⚠️ Spec Extraction Error (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return {}
            time.sleep(2 ** attempt)