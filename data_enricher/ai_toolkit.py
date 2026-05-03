import os
import json
import time
import re
import json_repair
from openai import OpenAI
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=os.getenv("FIREWORKS_API_KEY"),
    timeout=15.0
)

# ==========================================
# CORE UTILITIES
# ==========================================

def extract_json_from_text(raw_text: str):
    try:
        # Use the battle-tested deterministic parser wrapper!
        parsed_dict = json_repair.repair_json(raw_text, return_objects=True)
        if isinstance(parsed_dict, dict) and parsed_dict:
            return parsed_dict
        elif isinstance(parsed_dict, list) and len(parsed_dict) > 0 and isinstance(parsed_dict[0], dict):
            return parsed_dict[0]
            
        raise ValueError("Return type was not a dictionary")
    except Exception as e:
        # Raise the error so the upstream API retries with a new token generation sequence
        raise ValueError(f"JSON-Repair Structural Error: {e}")

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
            time.sleep(2) # Waits 1s, then 2s, then gives up

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
            time.sleep(2)

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
            time.sleep(2)

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
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            return extract_json_from_text(response.choices[0].message.content)
        except Exception as e:
            print(f"      ⚠️ Ghost Hunter API Error (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return {"description": "Not found", "specifications": {}}
            time.sleep(2)

# ==========================================
# TOOL 3: THE SCHEMA ROUTER
# ==========================================

def determine_schema(cat_string, schemas_dict):
    """
    Dynamically maps the database category string to the JSON schema.
    """
    if not cat_string:
        return schemas_dict.get("General", {})
        
    cat_lower = cat_string.lower()
    
    # 1. Custom Consolidations (Multi-to-One)
    if "laptop" in cat_lower and "bag" not in cat_lower and "stand" not in cat_lower and "cooling" not in cat_lower:
        return schemas_dict.get("Laptops", {})
    if "charger" in cat_lower:
        return schemas_dict.get("Chargers", {})
        
    # 2. Dynamic Schema Key Matching
    for schema_key in schemas_dict.keys():
        if schema_key == "General":
            continue
        # Check if the exact schema name (lowercased) exists anywhere in the giant category string
        if schema_key.lower() in cat_lower:
            return schemas_dict.get(schema_key)
            
    # Fallback safety net
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
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            return extract_json_from_text(response.choices[0].message.content)
        except Exception as e:
            print(f"      ⚠️ Spec Extraction Error (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return {}
            time.sleep(2)