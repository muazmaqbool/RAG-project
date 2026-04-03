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
                
                ai_recommendation = data.get("recommendation", "")
                products = data.get("products", [])
                
                if not products:
                    st.warning("No products found within that criteria. Try adjusting your budget!")
                else:
                    # --- 1. DISPLAY AI RECOMMENDATION ---
                    st.subheader("✨ The AI Verdict")
                    st.info(ai_recommendation)
                    
                    st.divider()
                    
                    # --- 2. DISPLAY PRODUCT CARDS ---
                    st.subheader("🛒 Top 5 Database Matches")
                    
                    # We will highlight the first result as the #1 Match
                    top_product = products[0]
                    other_products = products[1:]
                    
                    # Highlighted Card for the top match
                    with st.container(border=True):
                        st.markdown("### 🏆 #1 Best Match")
                        st.markdown(f"**[{top_product['title']}]({top_product['url']})**")
                        st.markdown(f"**Price:** <span style='color:#2e7d32; font-size:1.2em;'>{top_product['price']:,} PKR</span>", unsafe_allow_html=True)
                        st.write(top_product['description'])
                        st.caption(f"Semantic Match Score: {top_product['match_score']}%")
                    
                    st.write("---")
                    
                    # A grid of 2 columns for the remaining 4 products
                    col1, col2 = st.columns(2)
                    
                    for i, product in enumerate(other_products):
                        # Alternate between left and right columns
                        target_col = col1 if i % 2 == 0 else col2
                        
                        with target_col:
                            with st.container(border=True):
                                # Truncate long titles for UI cleanliness
                                short_title = product['title'][:60] + "..." if len(product['title']) > 60 else product['title']
                                st.markdown(f"**[{short_title}]({product['url']})**")
                                st.markdown(f"**Price:** {product['price']:,} PKR")
                                # Show only the first two sentences of the description to keep cards neat
                                short_desc = ".".join(product['description'].split('.')[:2]) + "."
                                st.write(short_desc)
                                st.caption(f"Match Score: {product['match_score']}%")

            except Exception as e:
                st.error(f"Failed to connect to the API. Make sure your FastAPI server is running! Error: {e}")
    else:
        st.warning("Please enter a search query first.")