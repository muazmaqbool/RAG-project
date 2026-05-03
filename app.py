import streamlit as st
import requests
import pandas as pd

# Configure the web page
st.set_page_config(page_title="AI Tech Store", page_icon="💻", layout="wide")

# The URL of your local FastAPI backend
API_URL = "http://127.0.0.1:8000/recommend"

# --- MAIN UI ---
st.title("🤖 AI Hardware Assistant")
st.markdown("Describe exactly what you need, and our RAG engine will find the perfect machine.")

# The Chat Search Bar
user_query = st.text_input("What are you looking for?", placeholder="e.g., A fast laptop for 3D rendering and gaming...")

if st.button("Search Inventory", type="primary"):
    if user_query:
        with st.spinner("Scanning database and consulting Mixtral AI..."):
            
            # Prepare the JSON payload for FastAPI
            payload = {
                "query": user_query,
                "top_k": 10,
                "min_price": None,
                "max_price": None
            }
            
            try:
                # Hit the backend
                response = requests.post(API_URL, json=payload)
                response.raise_for_status()
                data = response.json()
                
                explanation = data.get("explanation", "")
                top_picks = data.get("top_picks", [])
                alternatives = data.get("alternatives", [])
                
                if not top_picks and not alternatives:
                    st.warning("No products found within that criteria. Try adjusting your budget!")
                else:
                    # --- 1. DISPLAY AI VERDICT & LIST ---
                    st.subheader("✨ The AI Verdict")
                        
                    # Render the list and the LLM's explanation inside the blue info box
                    st.info(f"{explanation}")
                    
                    st.divider()
                    
                    # --- 2. DISPLAY MULTIPLE GOLD CARDS ---
                    st.subheader(f"🏆 Top Picks ({len(top_picks)} Items)")
                    
                    # Create a grid for the top picks if there are multiple
                    pick_cols = st.columns(len(top_picks)) if len(top_picks) > 1 else [st.container()]
                    
                    for i, pick in enumerate(top_picks):
                        target_col = pick_cols[i] if len(top_picks) > 1 else pick_cols[0]
                        with target_col:
                            with st.container(border=True):
                                st.markdown(f"### 🥇 Best {pick.get('matched_intent', 'Match')}")
                                st.markdown(f"**[{pick['title']}]({pick['url']})**")
                                
                                # --- Render Image for Top Picks ---
                                if pick.get('image_url'):
                                    st.image(pick['image_url'], use_container_width=True)
                                
                                st.markdown(f"**Price:** <span style='color:#2e7d32; font-size:1.2em;'>{pick['price']:,} PKR</span>", unsafe_allow_html=True)
                                # --- DYNAMIC SHORT DESCRIPTION ---
                                display_specs = pick.get('display_specs', {})
                                search_specs = pick.get('search_specs', {})
                                
                                # Use search_specs if available, otherwise display_specs
                                specs_dict = {k: v for k, v in search_specs.items() if v not in ("", None, [], {})}
                                if not specs_dict:
                                    specs_dict = {k: v for k, v in display_specs.items() if v not in ("", None, [], {})}
                                
                                if specs_dict:
                                    # 2. THE PRIORITY LIST: What matters most to buyers?
                                    # It will hunt for these keys first, in this exact order.
                                    priority_keys = [
                                        'processor_name', 'processor_brand', 'ram_gb', 'storage_ssd_gb', 
                                        'graphics_card_name', 'graphics_memory_gb', 'screen_size_inches'
                                    ]
                                    
                                    spec_lines = []
                                    
                                    # Step A: Pull the high-priority specs first
                                    for key in priority_keys:
                                        if key in specs_dict and specs_dict[key] not in ("", None, []):
                                            clean_key = str(key).replace('_', ' ').title()
                                            # Clean up common redundant keys (e.g. "Ram Gb" -> "RAM")
                                            clean_key = clean_key.replace('Gb', '(GB)').replace('Ram', 'RAM').replace('Ssd', 'SSD')
                                            
                                            spec_lines.append(f"- **{clean_key}**: {specs_dict[key]}")
                                                
                                    # Step B: Backfill with whatever else is available
                                    for k, v in specs_dict.items():
                                        if k not in priority_keys and v not in ("", None, []):
                                            clean_key = str(k).replace('_', ' ').title()
                                            spec_lines.append(f"- **{clean_key}**: {v}")

                                    short_desc = "\n".join(spec_lines)
                                    
                                else:
                                    # 3. Ultimate Fallback: Truncate original description
                                    raw_desc = pick.get('description', '')
                                    short_desc = raw_desc[:120] + "..." if len(raw_desc) > 120 else raw_desc
                                    
                                # Display the new, prioritized short description
                                st.markdown(short_desc)
                                            
                    st.write("---")
                    
                    # --- 3. DISPLAY ALTERNATIVES ---
                    if alternatives:
                        st.subheader("🛒 Other Great Options")
                        col1, col2 = st.columns(2)
                        
                        for i, product in enumerate(alternatives):
                            target_col = col1 if i % 2 == 0 else col2
                            
                            with target_col:
                                with st.container(border=True):
                                    # Add the category tag at the top of the card
                                    st.caption(f"Category: **{product.get('matched_intent', 'General')}**")
                                    
                                    short_title = product['title'][:60] + "..." if len(product['title']) > 60 else product['title']
                                    st.markdown(f"**[{short_title}]({product['url']})**")
                                    
                                    # --- Render Image for Alternatives ---
                                    if product.get('image_url'):
                                        st.image(product['image_url'], use_container_width=True)
                                        
                                    st.markdown(f"**Price:** {product['price']:,} PKR")
                                    short_desc = ".".join(product['description'].split('.')[:2]) + "."
                                    st.write(short_desc)
                                    st.caption(f"Match Score: {product['match_score']}%")

                    # --- 4. DISPLAY COMPARISON ---
                    all_items = top_picks + alternatives
                    
                    # Group items by matched_intent category
                    category_groups = {}
                    for item in all_items:
                        cat = item.get('matched_intent', 'General')
                        if cat not in category_groups:
                            category_groups[cat] = []
                        category_groups[cat].append(item)
                    
                    # See if any category has more than 1 item
                    categories_to_compare = {k: v for k, v in category_groups.items() if len(v) > 1}
                    
                    if categories_to_compare:
                        st.write("---")
                        st.subheader("⚖️ Compare Categories")
                        
                        for category, items in categories_to_compare.items():
                            with st.expander(f"Compare {category} ({len(items)} items)", expanded=False):
                                all_keys = set()
                                for item in items:
                                    specs = item.get('search_specs', {})
                                    if not specs:
                                        specs = item.get('display_specs', {})
                                    all_keys.update([k for k, v in specs.items() if v not in ("", None, [], {})])
                                
                                comp_data = {}
                                for item in items:
                                    p_name = item['title'][:35] + "..." if len(item['title']) > 35 else item['title']
                                    
                                    # Handle duplicate names
                                    base_name = p_name
                                    counter = 1
                                    while p_name in comp_data:
                                        p_name = f"{base_name} ({counter})"
                                        counter += 1
                                        
                                    p_specs = item.get('search_specs', {})
                                    if not p_specs:
                                        p_specs = item.get('display_specs', {})
                                        
                                    comp_data[p_name] = {"Price": f"{item['price']:,} PKR"}
                                    
                                    for k in sorted(all_keys):
                                        val = p_specs.get(k, "N/A")
                                        if val in ("", None, []): val = "N/A"
                                        clean_key = str(k).replace('_', ' ').title().replace('Gb', '(GB)').replace('Ram', 'RAM').replace('Ssd', 'SSD')
                                        comp_data[p_name][clean_key] = val
                                        
                                df = pd.DataFrame(comp_data)
                                st.dataframe(df, use_container_width=True)

            except Exception as e:
                st.error(f"Failed to connect to the API. Make sure your FastAPI server is running! Error: {e}")
    else:
        st.warning("Please enter a search query first.")