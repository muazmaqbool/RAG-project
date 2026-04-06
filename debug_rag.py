import json
from main import extract_search_intent_and_constraints, generate_query_vector, get_db_connection, evaluate_constraints

# The problematic query
QUERY = "powerbank with 65 watt input"

print("="*60)
print(f"🔍 DEBUGGING RAG PIPELINE FOR: '{QUERY}'")
print("="*60)

# --- STEP 1: WHAT DID THE LLM PLANNER EXTRACT? ---
print("\n[STEP 1: AGENT INTENT & CONSTRAINTS]")
intents = extract_search_intent_and_constraints(QUERY)
print(json.dumps(intents, indent=2))

if not intents:
    print("❌ Failed to extract any intents. Exiting.")
    exit()

item = intents[0]
constraints = item.get("constraints", [])

# --- STEP 2: WHAT DID THE VECTOR DB RETURN? ---
print("\n[STEP 2: RAW VECTOR SEARCH RESULTS (Before Math Filtering)]")
conn = get_db_connection()
cursor = conn.cursor()

vector = generate_query_vector(item["sub_query"])
sql = """
    SELECT title, price_pkr, 
           1 - (embedding <=> %s::vector) AS similarity_score,
           specifications, description
    FROM products
    WHERE is_available = True
"""
params = [vector]

if item.get("primary_category") and item.get("primary_category") != "General":
    sql += " AND categories::text ILIKE %s"
    params.append(f"%{item['primary_category']}%")
    
sql += " ORDER BY embedding <=> %s::vector LIMIT 10;"
params.extend([vector])

cursor.execute(sql, tuple(params))
raw_results = cursor.fetchall()

if not raw_results:
    print("❌ No results found in the database for this category/vector.")
    exit()

# --- STEP 3: HOW DID THE MATH ENGINE GRADE THEM? ---
print("\n[STEP 3: CONSTRAINT EVALUATION ENGINE]")
for i, r in enumerate(raw_results):
    title = r[0]
    score = r[2]
    specs = r[3]
    desc = r[4]
    
    # Run your exact filtering logic
    passed = evaluate_constraints(specs, title, desc, constraints)
    
    status_icon = "✅ PASSED" if passed else "❌ FAILED"
    
    print(f"\n{status_icon} | Match: {score*100:.1f}% | {title}")
    
    # Only print specs if it failed so we can see why it failed
    if not passed and constraints:
        print(f"   -> Let's check the extracted numbers...")
        # Print the numbers the fallback engine actually saw
        full_text = f"{title} {desc} " + " ".join([str(v) for v in (specs or {}).values()])
        import re
        all_numbers = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", full_text)]
        print(f"   -> Numbers found in text: {all_numbers[:10]}...") # Print first 10 numbers found

cursor.close()
conn.close()
print("\n" + "="*60)
print("🏁 DEBUG COMPLETE")