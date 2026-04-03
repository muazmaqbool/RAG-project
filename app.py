import streamlit as st
import requests

# Configure the web page
st.set_page_config(page_title="AI Tech Store", page_icon="💻", layout="wide")

# The URL of your local FastAPI backend
API_URL = "http://127.0.0.1:8000/recommend"

# --- SIDEBAR: FILTERS ---
with st.sidebar:
    st.header("Search Filters")
    st.write("Set your budget constraints:")
    
    # Optional price filters
    use_min = st.checkbox("Minimum Price")
    min_price = st.number_input("Min (PKR)", min_value=0, step=5000, value=50000) if use_min else None
    
    use_max = st.checkbox("Maximum Price")
    max_price = st.number_input("Max (PKR)", min_value=0, step=5000, value=200000) if use_max else None

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
                "top_k": 5,
                "min_price": min_price,
                "max_price": max_price
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
                    
                    # Dynamically build the bulleted list you requested
                    bullet_points = "**Recommendations:**\n"
                    for pick in top_picks:
                        category_name = pick.get('matched_intent', 'Item')
                        bullet_points += f"* **{category_name}:** [{pick['title']}]({pick['url']})\n"
                        
                    # Render the list and the LLM's explanation inside the blue info box
                    st.info(f"{bullet_points}\n\n{explanation}")
                    
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
                                st.markdown(f"**Price:** <span style='color:#2e7d32; font-size:1.2em;'>{pick['price']:,} PKR</span>", unsafe_allow_html=True)
                                st.write(pick['description'])
                                st.caption(f"Semantic Match Score: {pick['match_score']}%")
                    
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
                                    st.markdown(f"**Price:** {product['price']:,} PKR")
                                    short_desc = ".".join(product['description'].split('.')[:2]) + "."
                                    st.write(short_desc)
                                    st.caption(f"Match Score: {product['match_score']}%")

            except Exception as e:
                st.error(f"Failed to connect to the API. Make sure your FastAPI server is running! Error: {e}")
    else:
        st.warning("Please enter a search query first.")