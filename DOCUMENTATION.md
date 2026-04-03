# E-Commerce RAG System: Architecture & Data Engineering Documentation

## 1. Executive Summary

This documentation outlines the architecture, engineering decisions, and data flow of a custom Extract, Transform, Load (ETL) pipeline and Retrieval-Augmented Generation (RAG) backend designed for an e-commerce hardware platform. The system autonomously ingests raw, unstructured HTML product data and transforms it into a highly structured, semantically searchable vector database.

The core engineering achievement of this architecture is its resilient handling of sparse and incomplete data through tiered AI processing. The pipeline categorizes incomplete products and routes them through specialized workflows:
* **"Skeletons" (Specs without descriptions):** Processed via a high-speed prompt to draft localized marketing copy.
* **"Ghosts" (Titles with no specs or descriptions):** Routed to an autonomous **Agentic Search Workflow** that scrapes the live internet for context to deduce the missing technical specifications.

To power this, the system leverages a **Mixture of Experts (MoE)** Large Language Model, ensuring top-tier reasoning capabilities at extremely high speeds. The fully enriched dataset is ultimately loaded into a local database and served through a high-performance FastAPI backend. This API implements **Hybrid Search**—combining exact SQL metadata filtering (e.g., strict price ceilings) with high-dimensional vector similarity search—to deliver precise, context-aware product recommendations.

---

## 2. Tech Stack & Infrastructure

The technology stack was specifically selected to balance local data privacy and stability with the immense processing power of serverless, open-weight AI models.

### Core Orchestration & Extraction (Web Scraping)
* **Python 3**: The primary language for all orchestration scripts, ETL logic, and API development.
* **Requests & BeautifulSoup4**: Used for resilient, raw HTML fetching and DOM parsing. These libraries handle connection timeouts gracefully and extract taxonomy trees and nested HTML specification tables into clean Python dictionaries.

### AI & Machine Learning (Transformation)
* **Fireworks AI API**: Chosen as the primary inference engine due to its exceptional speed, cost-efficiency, and native compatibility with the OpenAI Python SDK.
* **Text Generation (The MoE Engine)**: `accounts/fireworks/models/mixtral-8x22b-instruct`. This Mixture of Experts model is used for all text generation and data deduction. It provides massive, 141-billion-parameter reasoning capabilities (vital for accurately structuring JSON from messy web searches) while only activating ~39 billion parameters during inference for rapid processing.
* **Vector Embeddings**: `nomic-ai/nomic-embed-text-v1.5`. A state-of-the-art embedding model selected specifically because it natively outputs **768-dimension vectors**. This precise dimensionality perfectly aligns with the mathematical constraints of standard database search indexes without requiring lossy API-side compression.
* **Agentic Search Tooling**: `duckduckgo-search`. An open-source library integrated into the "Ghost Hunter" script. It grants the LLM live web-browsing capabilities to resolve missing product data without requiring paid search APIs.

### Database & Backend (Loading & Serving)
* **PostgreSQL**: The core relational database used for storing all product metadata natively on the local machine.
* **pgvector Extension**: Enables Postgres to store high-dimensional arrays and execute rapid similarity searches using Hierarchical Navigable Small World (HNSW) indexes.
* **psycopg2-binary & psycopg2.extras**: Database adapters used for executing SQL queries and safely casting complex Python dictionaries into native Postgres `JSONB` data types.
* **FastAPI & Uvicorn**: The asynchronous web framework and ASGI server used to build the retrieval API. FastAPI was chosen for its native asynchronous execution, strict data validation via `pydantic`, and automatic OpenAPI (`/docs`) interface generation.
* **python-dotenv**: Utilized across all modules for secure environment variable and API key management.

## 3. The Engineering Journey: Pivots & Decisions

Building a robust ETL pipeline and RAG architecture is rarely a straight line. The final system design is the result of navigating strict hardware limitations, volatile third-party API ecosystems, and database physics. Below is a detailed breakdown of the architectural pivots made during development.

### 3.1 Failed & Abandoned Approaches
Understanding what *didn't* work is crucial to validating the final architecture.

* **Attempt 1: Fully Local Execution (Intel MacBook Pro 2017)**
    * *The Concept:* Run both the PostgreSQL database and the LLMs natively to ensure zero data egress and zero API costs.
    * *The Failure:* Hardware compute bottlenecks. While a 2017 Intel chip can easily handle local database hosting via Docker and small embedding models (like `all-MiniLM-L6-v2`), it utterly fails at generating text with quantized 8B+ parameter models. Generating 1,200 descriptions would have caused severe thermal throttling and taken an estimated 48 hours.
* **Attempt 2: Cloud GPU Provisioning (DigitalOcean/Paperspace)**
    * *The Concept:* Spin up an AMD GPU droplet to host a stateless FastAPI compute node, keeping the database local.
    * *The Failure:* Unforeseen account and regional credit restrictions on the cloud provider side prevented the deployment of the GPU instances, forcing a pivot back to serverless APIs.
* **Attempt 3: Google Gemini Native SDK & Free Tiers**
    * *The Concept:* Utilize Google's generous AI Studio free tier for both text generation (`gemini-1.5-flash`) and embeddings (`text-embedding-004`).
    * *The Failure:* We encountered a "bleeding-edge" ecosystem shift. Google deprecated the legacy `google.generativeai` package mid-development in favor of the new `google-genai` SDK. This caused regional 404 errors for the embedding endpoints. Furthermore, Google subsequently tightened their free-tier rate limits, making bulk data ingestion unviable.
* **Attempt 4: 3072-Dimension Vector Indexes in PostgreSQL**
    * *The Concept:* When upgrading to Google's newest multimodal model (`gemini-embedding-2-preview`), the output vector expanded from 768 to 3072 dimensions, promising incredibly high semantic resolution.
    * *The Failure:* The `pgvector` extension in PostgreSQL has a hard physical limitation: **it cannot build an HNSW (Hierarchical Navigable Small World) index for vectors exceeding 2,000 dimensions.** Attempting to index a 3072-dimension column resulted in fatal SQL `54000` errors.

### 3.2 Successful Architectural Decisions
The failures above forced resilient design patterns. Here are the core decisions that define the final, highly functional stack.

* **Decision 1: The "Medallion" Data Architecture (Decoupled ETL)**
    * *The Problem:* Reading scraped data and injecting it straight into the database via LLMs is dangerous; if the DB connection drops or the script crashes on product #1,199, the expensive AI processing is lost.
    * *The Solution:* We introduced a middle layer. The pipeline now reads `final_scraped_dataset.json` (Raw), uses AI to generate missing text and vectors, and saves it to a local `enriched_dataset.json` (Silver/Gold). Only when the JSON is 100% complete do we run a lightning-fast bulk SQL loader to push it to PostgreSQL. This ensures fault tolerance and decouples the rate-limited AI generation from database operations.
* **Decision 2: Transition to Fireworks AI & Mixture of Experts (MoE)**
    * *The Problem:* We needed an API that was extremely fast, cost-effective, and compatible with open-source tools.
    * *The Solution:* We pivoted to Fireworks AI (using the standard OpenAI Python SDK). We deployed `mixtral-8x22b-instruct`, a Mixture of Experts model. This provided the massive reasoning capabilities of a 141-billion parameter model (necessary for agentic search and complex JSON formatting) while running at the speed and cost of a much smaller model, processing the entire dataset for pennies.
* **Decision 3: Standardizing on Nomic 768-Dimension Embeddings**
    * *The Problem:* Bypassing the PostgreSQL 2,000-dimension limit without resorting to lossy, API-side mathematical compression.
    * *The Solution:* We switched our embedding engine to `nomic-ai/nomic-embed-text-v1.5`. Nomic is highly rated on the MTEB (Massive Text Embedding Benchmark) and natively outputs standard **768-dimension vectors**. This allowed us to build the high-speed HNSW index in Postgres flawlessly.
* **Decision 4: The Agentic "Ghost Hunter" Pattern**
    * *The Problem:* E-commerce scraping often yields "Ghosts"—products with just a title and no specifications. A standard LLM cannot write a description for a product it knows nothing about.
    * *The Solution:* We split the enrichment phase. Easy products are handled quickly by the main script. "Ghosts" are skipped and routed to `enrich_ghosts.py`. This script acts as an autonomous agent: it uses `duckduckgo-search` to scrape live internet results for the specific product, feeds that context into Mixtral-8x22B, and forces the model to deduce the specs and return a strict, formatted JSON object. 
* **Decision 5: Hybrid Search API (Solving the LLM Math Problem)**
    * *The Problem:* Vector embeddings map *semantic meaning* (e.g., "cheap", "high-end") but are notoriously terrible at enforcing hard numerical boundaries. Embedding the phrase "under 150000 PKR" will not prevent the vector search from returning a 300,000 PKR laptop if the descriptions are semantically similar.
    * *The Solution:* We implemented **Hybrid Search** in the FastAPI backend. The API receives the user's query and optional price parameters. It dynamically constructs a SQL query that applies hard relational filters (`WHERE price_pkr <= 150000`) *before* it calculates the Cosine Distance (`<=>`). This guarantees mathematical accuracy alongside semantic relevance.

## 4. Codebase Reference & Function Dictionary

This section provides a granular breakdown of the codebase, separated by the three distinct phases of the ETL pipeline. It details the specific libraries used, the core functions within each script, and the engineering rationale behind their design.

### Phase 1: Extraction (Web Scraping & DOM Parsing)

The extraction layer is responsible for mapping the target e-commerce website, handling network instability, and parsing raw HTML into structured Python dictionaries. 

**Core Libraries Used:**
* `requests`: Used for executing synchronous HTTP GET requests. We relied heavily on custom headers (spoofing modern browser User-Agents) and explicit timeouts (`timeout=15`) to prevent the scraper from hanging indefinitely on spotty server connections.
* `bs4` (BeautifulSoup4): The primary DOM parser. We utilized CSS selectors (`soup.select_one`) rather than regex or raw string manipulation for robust, scalable HTML extraction.
* `time` & `os`: Used for basic rate-limiting (`time.sleep`) to prevent IP bans, and checking file paths for the resumability logic.

---

#### Script: `taxonomy_mapper.py`
**Purpose:** To programmatically map the entire category structure of the e-commerce site before scraping individual products. This ensures every product is tagged with its correct hierarchical lineage (e.g., *Laptops > Dell > Latitude*).

* **`map_website_taxonomy(base_url)`:** The entry point that fetches the homepage HTML and locates the primary mega-menu container.
* **`extract_menu_nodes(ul_element)`:** A **recursive function** that digs through nested `<ul>` and `<li>` HTML tags. Recursion was chosen here because navigation menus have unpredictable depths. It calls itself whenever it detects a nested `mega-sub-menu`, building a complete JSON tree of the site's architecture.
* **`filter_taxonomy(nodes)`:** A cleanup utility. It iterates through the generated tree and prunes any branches that do not contain `/product-category/` or `/brand/` in their URLs, ensuring we don't accidentally scrape "Contact Us" or "Blog" pages.

#### Script: `catalog_crawler.py`
**Purpose:** To visit a specific category page (e.g., "All HP Laptops") and extract the direct URLs of every product listed on that grid.

* **`get_product_urls(category_url)`:** Fetches the category page and uses `soup.find_all('a', href=True)` to grab every single link. 
    * *Constraint Handling:* E-commerce grids often link to the same product multiple times (the image, the title, and the "Buy" button all share the same link). We pass the final list through a Python `set()` to instantly mathematically deduplicate the array.
    * *URL Filtering:* We explicitly check that the `href` contains `/product/` and does *not* contain `/product-category/` to prevent infinite crawling loops.

#### Script: `single_product.py` & `test_scraper.py`
**Purpose:** The targeted extraction logic for a single product page. These scripts were used to build and test the CSS selectors before deploying them at scale.

* **`scrape_product_page(url)` / `test_scrape_product(url)`:** The core HTML parsing function.
    * *DOM Extraction:* Uses exact CSS selectors (e.g., `h1.product_title`, `tr.sts-attr-row`) to locate data.
    * *Table Parsing:* Iterates through the HTML specification table, pairing `<th>` (keys) with `<td>` (values) to build a dynamic dictionary of technical specs.
    * *Data Cleaning (Price):* Implements robust string parsing to handle dirty data. It strips out currency symbols (`₨`), commas, and text. Most importantly, it includes conditional logic: if a price cannot be coerced into an integer, or if the string contains the word "call", it triggers a boolean flag `"is_call_for_price": True` and sets the integer value to `None`.

#### Script: `master_crawler.py`
**Purpose:** The orchestrator. This script loops through thousands of URLs, applies the extraction logic, and manages state, saving, and network errors.

* **`scrape_product_data(url, category_paths)`:** An enhanced version of the single product scraper with built-in fault tolerance.
    * *404 Handling:* If the server returns a `404 Not Found`, the function catches it and returns a "base schema" with `"is_available": False`. This prevents the script from crashing when products are removed from the live site.
    * *Network Drops:* Wrapped in a `try/except` block catching `requests.RequestException`. If the internet drops, it returns `None`, signaling the orchestrator to skip saving so the item can be retried on the next run.
* **Resumability Logic (Global Scope):** Before starting the massive URL loop, the script checks if `final_scraped_dataset.json` already exists. If it does, it loads the file, creates a `set()` of all successfully scraped URLs, and skips them in the `for` loop. This allows the user to stop and start the hours-long scraping process without losing a single byte of data.

### Phase 2: Transformation (AI Enrichment)

The transformation layer is where raw data becomes "smart" data. This phase cleans sparse entries, generates localized marketing copy, and maps every product into a mathematical vector space for semantic search. Because AI inference is expensive and rate-limited, this phase writes its output to a local JSON file (`enriched_dataset.json`) to decouple it from the database.

**Core Libraries Used:**
* `openai`: Used to interface with the Fireworks AI API (which natively supports the OpenAI SDK format).
* `duckduckgo_search`: A crucial open-source tool that allows the Python script to scrape live internet results for missing product context without requiring a paid search API key.
* `json` & `os`: Used for robust file handling and state management (resumability).

---

#### Script: `enrich_dataset.py` (The Workhorse)
**Purpose:** Iterates through the raw scraped dataset, identifies products with incomplete descriptions but intact specifications ("Skeletons"), and uses the Mixtral-8x22B MoE model to draft high-quality descriptions. It then generates 768-dimension vectors for all valid products.

* **`draft_missing_description(specs_dict)`:** Takes the raw dictionary of specifications and passes it to the `mixtral-8x22b-instruct` model with a low temperature (`0.3`) to prevent hallucination. It drafts a 4-sentence, buyer-focused description.
* **`generate_vector(text_chunk)`:** Concatenates the product's Title, Description, and Specs into a single string and passes it to `nomic-ai/nomic-embed-text-v1.5`. Returns a dense 768-dimension array.
* **`run_enrichment()`:** The main orchestrator loop. 
    * *The Triage Logic:* It counts the words in the description. If `word_count < 50` AND the product has specs, it calls the drafting function. If `word_count < 50` AND it lacks specs, it flags the product as a "Ghost", skips it, and leaves it for the next script.
    * *Resumability:* Checks if `enriched_dataset.json` exists. If so, it loads the previously processed URLs into a `set` and skips them, saving progress every 10 items to prevent data loss during API drops.

#### Script: `enrich_ghosts.py` (The Agentic Workflow)
**Purpose:** Specifically targets the obscure "Ghost" products skipped by the main script. It acts as an autonomous agent, searching the live web to deduce what the product is, structuring the findings into JSON, and embedding the results.

* **`search_web_for_product(product_title, brand)`:** Queries DuckDuckGo for the product title and extracts the text snippets from the top 3 live search results to build a contextual prompt.
* **`hunt_ghost_data(product_title, search_context)`:** The core agentic prompt. It feeds the live web snippets to Mixtral-8x22B. 
    * *Engineering Detail:* To prevent parsing errors, we enforce `response_format={"type": "json_object"}` in the API call, guaranteeing the model returns a perfectly structured dictionary with `description` and `specifications` keys.
* **`run_ghost_hunter()`:** Loads both the raw and enriched datasets. It isolates the skipped Ghost items, runs the web search and MoE extraction, generates the vector, and appends the newly recovered data directly into the master `enriched_dataset.json`.

---

### Phase 3: Loading & Serving

The final phase moves the fully processed "Gold Standard" JSON data into the production database and exposes it to end-users via a high-performance, asynchronous web API.

**Core Libraries Used:**
* `psycopg2` & `pgvector.psycopg2`: Adapters used to connect Python to PostgreSQL and specifically register support for vector math types.
* `fastapi` & `uvicorn`: The modern standard for Python APIs. FastAPI provides native async support, automatic documentation (`/docs`), and rigorous data validation.
* `pydantic`: Used to define strict schemas for incoming API requests.

---

#### Script: `load_to_db.py` (The Fast Loader)
**Purpose:** A lightweight, blazing-fast script that reads the 1,200+ products in the `enriched_dataset.json` and bulk-inserts them into the PostgreSQL database. Because all LLM processing is already done, this script executes in seconds.

* **`get_db_connection()`:** Connects to Postgres and runs `register_vector(conn)` so the database natively understands the Python vector arrays.
* **`load_data_to_db()`:** The bulk insertion loop.
    * *Idempotency:* Utilizes the Postgres `ON CONFLICT (url) DO UPDATE` command. If the script is run multiple times, it will seamlessly update existing rows rather than throwing duplicate key errors or crashing.
    * *JSONB Casting:* Uses `psycopg2.extras.Json()` to securely cast complex Python dictionaries (like the `specifications` object) into Postgres's native, searchable `JSONB` format, avoiding string-parsing errors.

#### Script: `main.py` (The Retrieval API)
**Purpose:** The user-facing search engine. It intercepts user queries, converts them to math, and executes a Hybrid Search against the Postgres database to return the best products.

* **`SearchQuery(BaseModel)`:** The Pydantic request model. It defines the expected JSON payload, requiring a `query` string, while allowing optional `top_k`, `min_price`, and `max_price` integer filters.
* **`generate_query_vector(text)`:** Embeds the user's search string (e.g., "fast laptop for coding") into a 768-dimension vector at runtime using the Nomic model.
* **`semantic_search(request)`:** The core endpoint (`POST /search`) that implements **Hybrid Search**.
    * *Dynamic SQL Construction:* It initializes a base SQL query. If the user provided `min_price` or `max_price`, it appends raw SQL `WHERE` clauses to the string to filter out products that violate the hard constraints *before* performing vector math.
    * *Vector Similarity:* Uses the pgvector `<=>` operator to calculate the Cosine Distance between the user's query vector and the database's product vectors. 
    * *Data Formatting:* Fetches the top `K` results, converts the mathematical distance into a human-readable `match_score` percentage, and returns the structured JSON payload to the user.

***

## 5. Future Roadmap & Deployment Strategy

With the ETL pipeline and vector retrieval engine fully operational, the foundation of the architecture is complete. The next phase of development focuses on synthesizing the retrieved data into natural language, building a user-facing interface, and deploying the system to the cloud using a strict zero-cost architecture.

### Phase 4: The Synthesis Layer (Completing the RAG)
Currently, the system successfully performs the "Retrieval" (R) and "Augmented" (A) steps by fetching the top 5 database results. The immediate next step is to implement the "Generation" (G) step.
* **The Conversational Endpoint:** We will build a new `/chat` endpoint in FastAPI.
* **The Logic:** This endpoint will intercept the 5 JSON products returned by our Hybrid Search, combine them with the user's original query, and pass them as context to `mixtral-8x22b-instruct`.
* **The Output:** Instead of returning raw JSON to the user, the system will return a conversational, AI-generated recommendation (e.g., *"Based on your budget of 150k, the best option is the HP Victus. It fits your price range and features an RTX 4050, which is perfect for your 3D rendering needs..."*).

### Phase 5: Frontend Interface
To make the system accessible to non-technical users and recruiters, we will build a lightweight web interface that interacts with the FastAPI backend.
* **Rapid Prototyping (Streamlit):** As an AI Developer, using a framework like **Streamlit** or **Gradio** allows us to build a beautiful, chat-based UI entirely in Python in under 50 lines of code. 
* **Full-Stack Alternative (React/Next.js):** If the goal is to showcase full-stack capabilities, a simple Next.js frontend with Tailwind CSS can be built to mimic a traditional e-commerce search bar and chat window.

### Phase 6: Zero-Cost Deployment Architecture
Deploying a database, an API, and a frontend usually incurs monthly cloud costs. We will bypass this by utilizing a modern serverless free-tier stack.

**Step 1: Local Testing & Port Forwarding (Week 1)**
Before pushing to the cloud, we will test the system locally. 
* We will use **Ngrok** or **Cloudflare Tunnels**. This securely exposes your MacBook's `localhost:8000` to the public internet via a temporary URL. You can share this link with friends or recruiters for a few days while running the backend from your laptop.

**Step 2: Cloud Database Migration (Supabase)**
Your local Dockerized PostgreSQL database needs to move to the cloud.
* **Supabase** offers a generous free tier for a cloud-hosted PostgreSQL database that has native `pgvector` support out of the box. We will simply change our `.env` credentials and run our `load_to_db.py` script one last time to populate the cloud database.

**Step 3: API & Frontend Hosting**
* **The Backend (Render or Hugging Face Spaces):** We will deploy the FastAPI `main.py` application to **Render** (Free Web Service tier) or **Hugging Face Spaces** (Free Docker tier). It will connect to the Supabase database and the Fireworks AI API.
* **The Frontend (Streamlit Community Cloud or Vercel):** If we build the UI in Streamlit, it can be hosted permanently for free on Streamlit Community Cloud. If we build a custom web app, we will host it on Vercel.

***