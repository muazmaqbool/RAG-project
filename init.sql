-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    price_pkr INTEGER,
    description TEXT,
    short_description TEXT,
    long_description TEXT,
    is_available BOOLEAN DEFAULT TRUE,
    is_call_for_price BOOLEAN,
    is_featured BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    image_urls JSONB,
    leaf_category TEXT,
    categories JSONB,
    search_specs JSONB,
    display_specs JSONB,
    embedding VECTOR(768)
);

-- HNSW Index for ultra-fast cosine similarity searches
CREATE INDEX IF NOT EXISTS products_embedding_idx ON products USING hnsw (embedding vector_cosine_ops);

-- GIN Index for rapid JSONB key/value filtering
CREATE INDEX IF NOT EXISTS products_search_specs_idx ON products USING gin (search_specs);

-- Create product_history table
CREATE TABLE IF NOT EXISTS product_history (
    id SERIAL PRIMARY KEY,
    url TEXT REFERENCES products(url) ON DELETE CASCADE,
    action TEXT,
    old_price INTEGER,
    new_price INTEGER,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create media_gallery table
CREATE TABLE IF NOT EXISTS media_gallery (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    url TEXT REFERENCES products(url) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- For test_db.py which specifically requests 'alaqsa' db
-- It's easier to just use the default 'postgres' database, but to ensure compatibility
-- we create a new user/db if needed, though usually just running the tests against
-- postgres will suffice by changing test_db.py.
