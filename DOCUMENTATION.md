# E-Commerce RAG System: Architecture & Data Engineering Documentation

## 1. Executive Summary

This documentation outlines the architecture, engineering decisions, and data flow of a custom Extract, Transform, Load (ETL) pipeline and Retrieval-Augmented Generation (RAG) backend designed for an e-commerce hardware platform. The system autonomously ingests raw, unstructured HTML product data and transforms it into a highly structured, semantically searchable vector database.

The core engineering achievement of this architecture is its resilient, idempotent **Change Data Capture (CDC)** pipeline. Instead of running expensive batch operations, a unified orchestrator calculates the delta between the live website and the local database. It categorizes incomplete new products and routes them through a modular, tiered AI toolkit:
* **"Skeletons" (Specs without descriptions):** Routed to a high-speed copywriter agent to draft localized, SEO-friendly marketing copy.
* **"Ghosts" (Titles with no specs or descriptions):** Routed to an autonomous **Agentic Search Workflow** that scrapes the live internet for context to deduce the missing technical specifications.

To power this, the system leverages a **Mixture of Experts (MoE)** Large Language Model, ensuring top-tier reasoning capabilities at extremely high speeds. The transformed data utilizes a **Dual-Layer Schema** (separating strict mathematical search parameters from human-readable UI specs) before being synced to a local database and served through a high-performance FastAPI backend. This API implements **Hybrid Search**—combining exact SQL metadata filtering with high-dimensional vector similarity search—to deliver precise, context-aware product recommendations.

---

## 2. Tech Stack & Infrastructure

The technology stack was specifically selected to balance local data privacy and stability with the immense processing power of serverless, open-weight AI models.

### Core Orchestration & Extraction (Web Scraping)
* **Python 3**: The primary language for all orchestration scripts, modular ETL logic, and API development.
* **Requests & BeautifulSoup4**: Used for resilient, raw HTML fetching and DOM parsing. These libraries handle connection timeouts gracefully and extract taxonomy trees and nested HTML specification tables into clean Python dictionaries.

### AI & Machine Learning (Transformation)
* **Fireworks AI API**: Chosen as the primary inference engine due to its exceptional speed, cost-efficiency, and native compatibility with the OpenAI Python SDK.
* **Text Generation (The MoE Engine)**: `accounts/fireworks/models/mixtral-8x22b-instruct`. This Mixture of Experts model is used for all text generation and data deduction. It provides massive, 141-billion-parameter reasoning capabilities (vital for accurately structuring JSON from messy web searches) while only activating ~39 billion parameters during inference for rapid processing.
* **Vector Embeddings**: `nomic-ai/nomic-embed-text-v1.5`. A state-of-the-art embedding model selected specifically because it natively outputs **768-dimension vectors**. This precise dimensionality perfectly aligns with the mathematical constraints of standard database search indexes without requiring lossy API-side compression.
* **Agentic Search Tooling**: `duckduckgo-search`. An open-source library integrated into the AI Toolkit. It grants the LLM live web-browsing capabilities to resolve missing product data without requiring paid search APIs.

### Database & Backend (Loading & Serving)
* **PostgreSQL**: The core relational database used for storing all product metadata natively on the local machine.
* **pgvector Extension**: Enables Postgres to store high-dimensional arrays and execute rapid similarity searches using Hierarchical Navigable Small World (HNSW) indexes.
* **psycopg2-binary & psycopg2.extras**: Database adapters used for executing bulk SQL queries (`execute_values`) and safely casting complex Python dictionaries into native Postgres `JSONB` data types.
* **FastAPI & Uvicorn**: The asynchronous web framework and ASGI server used to build the retrieval API. FastAPI was chosen for its native asynchronous execution, strict data validation via `pydantic`, and automatic OpenAPI (`/docs`) interface generation.

---

## 3. The Engineering Journey: Pivots & Decisions

Building a robust ETL pipeline and RAG architecture is rarely a straight line. The final system design is the result of navigating strict hardware limitations, volatile third-party API ecosystems, and database physics. Below is a detailed breakdown of the architectural pivots made during development.

### 3.1 Failed & Abandoned Approaches
Understanding what *didn't* work is crucial to validating the final architecture.

* **Attempt 1: Fully Local Execution (Intel MacBook Pro 2017)**
    * *The Failure:* Hardware compute bottlenecks. While a 2017 Intel chip can handle local databases and small embedding models, it utterly fails at generating text with quantized 8B+ parameter models. Generating 1,200 descriptions would have caused severe thermal throttling and taken an estimated 48 hours.
* **Attempt 2: Cloud GPU Provisioning (DigitalOcean/Paperspace)**
    * *The Failure:* Unforeseen account and regional credit restrictions on the cloud provider side prevented the deployment of the GPU instances, forcing a pivot back to serverless APIs.
* **Attempt 3: Google Gemini Native SDK & Free Tiers**
    * *The Failure:* We encountered a "bleeding-edge" ecosystem shift. Google deprecated the legacy package mid-development in favor of the new `google-genai` SDK, causing regional 404 errors. Furthermore, tightened free-tier rate limits made bulk data ingestion unviable.
* **Attempt 4: 3072-Dimension Vector Indexes in PostgreSQL**
    * *The Failure:* The `pgvector` extension in PostgreSQL has a hard physical limitation: **it cannot build an HNSW index for vectors exceeding 2,000 dimensions.** Attempting to index a 3072-dimension column from a newer multimodal model resulted in fatal SQL `54000` errors.

### 3.2 Successful Architectural Decisions
The failures above forced resilient design patterns. Here are the core decisions that define the final, highly functional stack.

* **Decision 1: The Unified CDC Orchestrator (Single-Flow Pipeline)**
    * *The Problem:* Initially, the pipeline used a fragmented batch-processing architecture that resulted in redundant LLM API calls and high file I/O overhead.
    * *The Solution:* We pivoted to a unified 7-step Change Data Capture (CDC) pipeline (`daily_update.py`). The script calculates the mathematical delta between the live website and the local database. It skips existing products, processes only new URLs using a modular AI Toolkit, soft-deletes missing products, and executes a lightning-fast UPSERT into PostgreSQL. This guarantees complete idempotency.
* **Decision 2: Transition to Fireworks AI & Mixture of Experts (MoE)**
    * *The Solution:* We deployed `mixtral-8x22b-instruct` via Fireworks AI. This provided the massive reasoning capabilities of a 141-billion parameter model (necessary for agentic search and complex JSON formatting) while running at the speed and cost of a much smaller model.
* **Decision 3: Standardizing on Nomic 768-Dimension Embeddings**
    * *The Solution:* We switched our embedding engine to `nomic-ai/nomic-embed-text-v1.5`. Nomic natively outputs standard **768-dimension vectors**, allowing us to build high-speed HNSW indexes in Postgres flawlessly.
* **Decision 4: Centralized AI Toolkit & The Agentic "Ghost Hunter"**
    * *The Problem:* E-commerce scraping yields "Ghosts"—products with just a title and no specifications. A standard LLM cannot write descriptions for products it knows nothing about.
    * *The Solution:* We centralized all LLM calls into a modular `ai_toolkit.py`. If the orchestrator detects a "Ghost", it triggers the web-search agent. It uses `duckduckgo-search` to scrape live internet results, feeds that context into Mixtral, and forces the model to deduce the specs and return a strict, formatted JSON object.
* **Decision 5: Dual-Layer Schema Optimization**
    * *The Problem:* Forcing an LLM to rewrite human-readable specifications it had already extracted was a massive waste of API tokens and time.
    * *The Solution:* We implemented a Dual-Layer Database Schema. The raw, messy specifications scraped from the DOM are passed directly to `display_specs` for the frontend UI. The LLM is then used *exclusively* to extract strict numeric/boolean data into `search_specs` for SQL filtering, cutting API costs by nearly 50%.
* **Decision 6: Hybrid Search API (Solving the LLM Math Problem)**
    * *The Problem:* Vector embeddings map *semantic meaning* but are notoriously terrible at enforcing hard numerical boundaries (e.g., "under 150000 PKR").
    * *The Solution:* We implemented **Hybrid Search** in the FastAPI backend. The API dynamically constructs a SQL query that applies hard relational filters (`WHERE price_pkr <= 150000`) *before* calculating Cosine Distance (`<=>`), guaranteeing mathematical accuracy alongside semantic relevance.
* **Decision 7: Transition from Single-Vector to Multi-Vector Search**
    * *The Problem:* "Attention Drift." When a user provided a multi-item prompt ("laptop and headphones"), the embedding model averaged the meanings, returning mixed, inaccurate results.
    * *The Solution:* Implemented **Agentic Query Decomposition**. An LLM breaks a single complex string into an array of isolated sub-queries. We generate a unique vector for *each* sub-query and execute parallel database searches using `asyncio.gather`, ensuring focused results.
* **Decision 8: Robust JSON Extraction (The "Chatty AI" Shield)**
    * *The Problem:* Smaller LLMs often wrap JSON output in conversational filler or Markdown backticks, crashing Python's `json.loads()`.
    * *The Solution:* Developed a resilient string-slicing utility in the `ai_toolkit.py` that isolates the `{` and `}` blocks, making the pipeline impervious to model updates or conversational "chattiness."

## 4. Codebase Reference & Function Dictionary

This section provides a granular breakdown of the codebase, separated by the distinct phases of the ETL pipeline and the retrieval engine. The architecture has been rigorously refactored to eliminate redundancy, centralizing all LLM logic into a single toolkit and managing the entire pipeline through a unified orchestrator.

### Phase 1: Extraction (`scrapers/`)
The extraction layer maps the target e-commerce website, handles network instability, and parses raw HTML into structured Python dictionaries. It operates entirely independently of the AI layer to ensure network delays do not waste compute time.

#### Script: `scrapers/url_crawler.py`
**Purpose:** Programmatically maps the category structure and handles pagination to build a deduplicated master list of every active product URL.
* **`map_website_taxonomy(base_url)`:** A recursive DOM parser that digs through nested `<ul>` and `<li>` mega-menu tags to build a complete JSON tree of the site's architecture.
* **`get_product_urls(base_category_url)`:** Handles site pagination natively. It converts relative links to absolute URLs via `urljoin` and utilizes Python `set()` mathematics to prevent crawling duplicate URLs.

#### Script: `scrapers/master_crawler.py`
**Purpose:** Iterates through the master URL list, applies CSS-selector extraction logic, and manages state/saving.
* **`scrape_product_data(url, category_paths)`:** The core HTML parser. It extracts the title, price, description, and nested HTML specification tables.
    * *Fault Tolerance:* If the server returns a `404 Not Found`, or the connection drops (`requests.RequestException`), it returns a "base schema" with `"is_available": False`. This prevents the script from crashing and accurately signals to the database that an item has been delisted.
* **Resumability Logic:** It actively reads the output file (`todays_scrape.json`). If the script crashes or is paused, it loads previously successful URLs into memory and skips them, ensuring zero wasted network calls.

---

### Phase 2: Transformation (`data_enricher/`)
This module acts as the "Single Source of Truth" for all AI and mathematical transformations. It contains highly optimized prompt templates and automatic retry mechanisms to handle API volatility.

#### Script: `data_enricher/ai_toolkit.py`
**Purpose:** A centralized library of LLM tools and vector generation utilities called by the daily orchestrator.
* **`generate_vector(text_chunk)`:** Interfaces with the Fireworks API to generate 768-dimension vectors using `nomic-embed-text-v1.5`. Includes an exponential backoff retry loop to survive rate limits.
* **`extract_search_specs(...)`:** The core of the **Dual-Layer Schema** optimization. It forces the MoE model to extract only strict, mathematically filterable data (integers, booleans) based on the target schema, explicitly ignoring qualitative descriptions to save API tokens.
* **`draft_missing_description(specs_dict, title)`:** The Copywriter Agent. Used for "Skeleton" products. It drafts 4-sentence SEO descriptions by weaving in strategic search intents (e.g., "Gaming," "Budget") derived strictly from the hardware specs.
* **`search_web_for_product` & `hunt_ghost_data`:** The Agentic Search Workflow. Triggered for products lacking both specs and descriptions. It leverages DuckDuckGo to scrape real-world context and forces the MoE model to deduce the missing structured JSON data.
* **`extract_json_from_text(raw_text)`:** A defensive string-slicing utility that prevents the pipeline from crashing if the LLM wraps its output in conversational markdown (e.g., ` ```json `).

---

### Phase 3: Orchestration & Loading
This phase calculates the delta between the live website and the database, routing only *new* or *changed* data through the expensive AI toolkit before syncing natively to PostgreSQL.

#### Script: `daily_update.py` (The 7-Step CDC Orchestrator)
**Purpose:** The central nervous system of the ETL pipeline. It executes a Change Data Capture (CDC) workflow to ensure the PostgreSQL database perfectly mirrors the live site with minimal compute overhead.
1. **Trigger Crawlers:** Executes the URL and DOM scrapers.
2. **Delta Routing:** Loads the master DB and today's scrape into memory. If a URL exists in both, it instantly updates the price and availability (Fast Path).
3. **Categorization:** If a URL is new, it analyzes the word count and schema keys to route it to the proper AI tool.
4. **Copywriting / Ghost Hunting:** Triggers the necessary AI agents from the toolkit to patch missing data.
5. **Strict Spec Extraction:** Generates the `search_specs` JSON object using the LLM, while preserving the raw scraped specs as `display_specs`.
6. **Soft Deletion:** Performs Set mathematics (`Master_DB_URLs - Todays_URLs`) to identify items removed from the website and flags them `is_available = False` (preserving historical vector data without polluting active search results).
7. **Database Sync (`sync_to_postgres`):** Uses `psycopg2.extras.execute_values` to perform a blazing-fast, idempotent `ON CONFLICT DO UPDATE` bulk insert into the local Postgres database.

---

### Phase 4: Serving (The Retrieval API)
The user-facing search engine that intercepts queries, converts them to math, and executes a Hybrid Search.

#### Script: `main.py` (FastAPI Backend)
**Purpose:** Exposes the vector database to the frontend via asynchronous HTTP endpoints.
* **`plan_search_intents(user_query)`:** The Query Decomposer. Breaks complex user prompts (e.g., "laptop and a mouse") into an array of isolated JSON sub-queries mapped to the official database taxonomy.
* **`semantic_search(request)`:** Generates a vector for the query and dynamically constructs a **Hybrid Search SQL statement**. It applies hard relational `JSONB` filters (e.g., strict budget limits, specific RAM requirements) *before* calculating Cosine Distance (`<=>`), guaranteeing mathematical accuracy alongside semantic relevance.
* **`get_ai_recommendation(request)`:** The Synthesis Layer. Reorders database results to align with AI reasoning, explaining *why* the recommended hardware fits the user's prompt based on the retrieved specs.

#### Script: `app.py` (Streamlit Frontend)
**Purpose:** A lightweight, rapid-prototyping UI that allows users to chat with the hardware assistant and view dynamic product recommendation cards with high-resolution metadata.

---

### Phase 5: Administration & Maintenance (`utils/`)
Utility scripts isolated from the daily pipeline, reserved for disaster recovery and future expansion.

* **`load_to_db.py`:** A disaster-recovery tool. If the PostgreSQL database is accidentally dropped, this script blasts the local `dual_layer_dataset.json` backup directly into the DB in seconds without requiring AI reprocessing.
* **`extract_specs.py`:** A schema-bootstrapping tool. Used when the store expands into brand-new product categories (e.g., Smart TVs). It scans the raw scraped DOM data and prints a list of all unique spec keys found in the wild to aid in building new `master_schema.json` rules.


## 5. Data Modeling & Database Schema

The core of the RAG system's speed and mathematical accuracy lies in its PostgreSQL schema. By leveraging native Postgres `JSONB` data types alongside the `pgvector` extension, the database acts as both a traditional relational store and a high-performance vector index.

### The `products` Table
```sql
CREATE TABLE products (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    price_pkr INTEGER,
    description TEXT,
    is_available BOOLEAN DEFAULT TRUE,
    is_call_for_price BOOLEAN,
    categories JSONB,
    search_specs JSONB,  -- Strict mathematical parameters for SQL filtering
    display_specs JSONB, -- Human-readable parameters for UI rendering
    embedding VECTOR(768) -- Nomic generated semantic mapping
);

-- HNSW Index for ultra-fast cosine similarity searches
CREATE INDEX ON products USING hnsw (embedding vector_cosine_ops);
-- GIN Index for rapid JSONB key/value filtering
CREATE INDEX ON products USING gin (search_specs);
```

### The Dual-Layer Schema Design
The separation of `search_specs` and `display_specs` is a primary cost-saving and performance architecture:
1. **`display_specs` (Raw/Messy):** Contains the exact, unstructured HTML tables scraped from the website (e.g., `{"Battery Life": "Up to 12.5 hours on mixed usage"}`). Saved without LLM processing.
2. **`search_specs` (Strict/Clean):** Driven by `master_schema.json`, the LLM extracts only mathematically filterable integers, floats, and booleans (e.g., `{"battery_life_hours": 12.5}`). This allows the FastAPI backend to execute hard SQL constraints (`search_specs @> '{"has_bluetooth": true}'`) without string-parsing errors.

---

## 6. Environment & Configuration

To run this pipeline and backend locally, the following environment variables must be configured in a `.env` file at the root directory. The pipeline is fully functional on the free tiers of these services.

```env
# AI Inference (Fireworks API)
FIREWORKS_API_KEY=your_fireworks_api_key_here

# PostgreSQL Database Credentials
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your_database_password
```

---

## 7. Future Roadmap & Deployment Strategy

With the autonomous CDC pipeline and vector retrieval engine fully operational, the foundation of the architecture is complete. The next phase focuses on synthesizing the retrieved data into natural language, building a user-facing interface, and deploying the system to the cloud using a zero-cost architecture.

### Phase 1: The Synthesis Layer (Completing the RAG)
Currently, the system successfully performs the "Retrieval" (R) and "Augmentation" (A) steps by fetching the top 5 database results. The immediate next step is to implement the "Generation" (G) step.
* **The Conversational Endpoint:** Build a new `/chat` endpoint in FastAPI.
* **The Logic:** Intercept the JSON products returned by the Hybrid Search, combine them with the user's original query, and pass them as context to `mixtral-8x22b-instruct`.
* **The Output:** Return a conversational, AI-generated recommendation (e.g., *"Based on your budget of 150k, the best option is the HP Victus. It fits your price range and features an RTX 4050, which is perfect for your 3D rendering needs..."*).

### Phase 2: Frontend Interface
To make the system accessible to non-technical users and recruiters, we will build a lightweight web interface that interacts with the FastAPI backend.
* **Rapid Prototyping (Streamlit):** Using Streamlit allows us to build a beautiful, chat-based UI natively in Python.
* **Full-Stack Alternative:** A Next.js frontend with Tailwind CSS can be built to mimic a traditional e-commerce search bar and chat window for a more native web experience.

### Phase 3: Zero-Cost Cloud Deployment
Deploying a vector database, an API, and a frontend usually incurs monthly cloud costs. We will bypass this by utilizing a modern serverless free-tier stack.
1. **Cloud Database Migration (Supabase):** Move the local Dockerized PostgreSQL database to Supabase, which offers a generous free tier for cloud-hosted Postgres with native `pgvector` support.
2. **API Hosting (Render / Hugging Face Spaces):** Deploy the FastAPI `main.py` application to Render (Free Web Service tier) or Hugging Face Spaces (Free Docker tier).
3. **Frontend Hosting (Streamlit Cloud):** Host the Streamlit UI permanently for free on Streamlit Community Cloud, pointing its API requests to the deployed backend.