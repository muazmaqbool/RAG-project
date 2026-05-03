"""
Admin-only API endpoints.
All routes require a valid X-Admin-Key header matched against ADMIN_SECRET_KEY env var.
"""
import os
import json
import uuid
import shutil
import asyncio
from typing import Optional
from datetime import datetime

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Header, Depends, UploadFile, File
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------
def require_admin(x_admin_key: Optional[str] = Header(None)):
    """Validates the X-Admin-Key header against the ADMIN_SECRET_KEY env variable."""
    expected = os.getenv("ADMIN_SECRET_KEY", "")
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_SECRET_KEY not configured on server")
    if x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")


def get_db():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class ProductWrite(BaseModel):
    url: str
    title: str
    price_pkr: Optional[int] = None
    original_price_pkr: Optional[int] = None
    is_call_for_price: bool = False
    is_available: bool = True
    is_featured: bool = False
    image_url: Optional[str] = None
    image_urls: Optional[list] = None
    leaf_category: Optional[str] = None
    categories: Optional[list] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    display_specs: Optional[dict] = None
    search_specs: Optional[dict] = None


class ProductUpdate(BaseModel):
    """Partial update — all fields optional. Only provided fields are updated."""
    title: Optional[str] = None
    price_pkr: Optional[int] = None
    original_price_pkr: Optional[int] = None
    is_call_for_price: Optional[bool] = None
    is_available: Optional[bool] = None
    is_featured: Optional[bool] = None
    image_url: Optional[str] = None
    image_urls: Optional[list] = None
    leaf_category: Optional[str] = None
    categories: Optional[list] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    display_specs: Optional[dict] = None
    search_specs: Optional[dict] = None


# ---------------------------------------------------------------------------
# Embedding helper (async, calls existing generate_vector in main.py context)
# We import lazily to avoid circular imports if main.py imports this module.
# ---------------------------------------------------------------------------
async def _make_embedding(text: str) -> Optional[list]:
    """Generates a pgvector-compatible embedding for the given text."""
    try:
        from main import generate_vector  # noqa: PLC0415
        return await generate_vector(text)
    except Exception as e:
        print(f"⚠️ Embedding generation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# POST /api/admin/products — create a new product
# ---------------------------------------------------------------------------
@router.post("/products", status_code=201, dependencies=[Depends(require_admin)])
async def create_product(product: ProductWrite):
    """
    Creates a new product row.
    If search_specs is not provided, an embedding is still generated from title + long_description.
    """
    embed_text = f"Title: {product.title}\nDescription: {product.long_description or ''}\nSpecs: {json.dumps(product.search_specs or {})}"
    embedding = await _make_embedding(embed_text)

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO products
                (url, title, price_pkr, is_call_for_price, is_available, image_url, image_urls,
                 leaf_category, categories, short_description, long_description,
                 description, display_specs, search_specs, embedding)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s::jsonb, %s::vector)
            RETURNING id
            """,
            (
                product.url,
                product.title,
                product.price_pkr,
                product.is_call_for_price,
                product.is_available,
                product.image_url,
                json.dumps(product.image_urls or []),
                product.leaf_category,
                json.dumps(product.categories or []),
                product.short_description,
                product.long_description,
                product.long_description,   # keep legacy `description` in sync
                json.dumps(product.display_specs or {}),
                json.dumps(product.search_specs or {}),
                embedding,
            ),
        )
        new_id = cur.fetchone()["id"]
        conn.commit()

        # Log creation in history
        cur.execute(
            "INSERT INTO product_history (url, action, old_price, new_price, changed_at) VALUES (%s, %s, %s, %s, %s)",
            (product.url, "ADDED", None, product.price_pkr, datetime.utcnow()),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        cur.close()
        conn.close()

    return {"id": new_id, "message": "Product created successfully"}


# ---------------------------------------------------------------------------
# PUT /api/admin/products/{product_id} — partial update
# ---------------------------------------------------------------------------
@router.put("/products/{product_id}", dependencies=[Depends(require_admin)])
async def update_product(product_id: int, updates: ProductUpdate):
    """
    Partially updates a product. Only fields present in the request body are changed.
    Re-generates embedding if title or long_description changes.
    """
    conn = get_db()
    cur = conn.cursor()

    # Fetch existing to detect price change and build embedding text
    cur.execute(
        "SELECT title, price_pkr, long_description, search_specs, url FROM products WHERE id = %s",
        (product_id,),
    )
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    # Build SET clause dynamically from provided fields
    update_data = updates.model_dump(exclude_none=True)

    # Regenerate embedding if content fields changed
    should_reembed = "title" in update_data or "long_description" in update_data or "search_specs" in update_data
    if should_reembed:
        new_title = update_data.get("title", existing["title"])
        new_desc = update_data.get("long_description", existing["long_description"] or "")
        new_specs = update_data.get("search_specs", existing["search_specs"] or {})
        embed_text = f"Title: {new_title}\nDescription: {new_desc}\nSpecs: {json.dumps(new_specs)}"
        embedding = await _make_embedding(embed_text)
        if embedding:
            update_data["embedding"] = embedding

    # Keep legacy description column in sync
    if "long_description" in update_data:
        update_data["description"] = update_data["long_description"]

    # Serialize JSON fields
    for json_field in ("categories", "display_specs", "search_specs", "image_urls"):
        if json_field in update_data:
            update_data[json_field] = json.dumps(update_data[json_field])

    if not update_data:
        cur.close()
        conn.close()
        return {"message": "No changes provided"}

    set_parts = []
    params = []
    for col, val in update_data.items():
        if col == "embedding":
            set_parts.append(f"{col} = %s::vector")
        elif col in ("categories", "display_specs", "search_specs", "image_urls"):
            set_parts.append(f"{col} = %s::jsonb")
        else:
            set_parts.append(f"{col} = %s")
        params.append(val)
    params.append(product_id)

    try:
        cur.execute(
            f"UPDATE products SET {', '.join(set_parts)} WHERE id = %s",
            params,
        )
        conn.commit()

        # Log price change to history if applicable
        if "price_pkr" in updates.model_dump(exclude_none=True):
            new_price = updates.price_pkr
            old_price = existing["price_pkr"]
            if old_price != new_price:
                cur.execute(
                    "INSERT INTO product_history (url, action, old_price, new_price, changed_at) VALUES (%s, %s, %s, %s, %s)",
                    (existing["url"], "PRICE_CHANGED", old_price, new_price, datetime.utcnow()),
                )
                conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        cur.close()
        conn.close()

    return {"message": "Product updated successfully"}


# ---------------------------------------------------------------------------
# DELETE /api/admin/products/{product_id} — soft delete
# ---------------------------------------------------------------------------
@router.delete("/products/{product_id}", dependencies=[Depends(require_admin)])
def delete_product(product_id: int):
    """
    Soft-deletes a product by setting is_available = FALSE.
    Writes a REMOVED entry to product_history.
    Hard deletion is intentionally avoided to preserve history integrity.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT url, price_pkr FROM products WHERE id = %s",
        (product_id,),
    )
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        cur.execute(
            "UPDATE products SET is_available = FALSE WHERE id = %s",
            (product_id,),
        )
        cur.execute(
            "INSERT INTO product_history (url, action, old_price, new_price, changed_at) VALUES (%s, %s, %s, %s, %s)",
            (existing["url"], "REMOVED", existing["price_pkr"], None, datetime.utcnow()),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        cur.close()
        conn.close()

    return {"message": "Product soft-deleted and history logged"}


# ---------------------------------------------------------------------------
# PATCH /api/admin/products/{product_id}/toggle-featured
# ---------------------------------------------------------------------------
@router.patch("/products/{product_id}/toggle-featured", dependencies=[Depends(require_admin)])
def toggle_featured(product_id: int):
    """Toggles is_featured for a product. Returns the new state."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT is_featured FROM products WHERE id = %s", (product_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
    new_state = not row["is_featured"]
    try:
        cur.execute("UPDATE products SET is_featured = %s WHERE id = %s", (new_state, product_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        cur.close(); conn.close()
    return {"id": product_id, "is_featured": new_state}


# ---------------------------------------------------------------------------
# POST /api/admin/products/{product_id}/enrich — run AI pipeline on one product
# ---------------------------------------------------------------------------
@router.post("/products/{product_id}/enrich", dependencies=[Depends(require_admin)])
async def enrich_product(product_id: int):
    """
    Runs the full AI enrichment pipeline on a single product:
    - Web search fallback if description is thin
    - Generates short_description (bullet HTML) and long_description (rich HTML)
    - Extracts search_specs using the category schema
    - Regenerates the pgvector embedding
    Updates the DB row and returns the enriched product data.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, url, title, long_description, short_description,
               display_specs, search_specs, leaf_category, categories, price_pkr
        FROM products WHERE id = %s
        """,
        (product_id,),
    )
    product = cur.fetchone()
    if not product:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    product = dict(product)

    # Import AI toolkit functions (sync — run in thread pool to avoid blocking event loop)
    try:
        from data_enricher.ai_toolkit import (  # noqa: PLC0415
            search_web_for_product,
            hunt_ghost_data,
            draft_missing_description,
            generate_vector as sync_generate_vector,
            determine_schema,
            extract_search_specs,
        )
        import json as _json  # noqa: PLC0415
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"AI toolkit import error: {e}")

    # Load master schema
    SCHEMA_PATH = "data/processed/master_schema.json"
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schemas = _json.load(f)
    else:
        schemas = {"General": {}}

    title = product["title"]
    raw_cats = product.get("categories") or []
    cat_string = " | ".join(raw_cats).lower() if raw_cats else "general"
    cat_path = max(raw_cats, key=len) if raw_cats else "General"
    brand = cat_path.split(">")[-1].strip() if "Brands" in cat_path else ""

    existing_long = product.get("long_description") or ""
    existing_specs = product.get("display_specs") or {}
    word_count = len(existing_long.split())

    # --- Run sync AI calls in thread pool ---
    def run_enrichment():
        desc = existing_long
        specs = existing_specs

        # If description is thin, search the web for more info
        if word_count < 50 and not specs:
            web_ctx = search_web_for_product(title, brand)
            ghost = hunt_ghost_data(title, web_ctx)
            if ghost.get("description") != "Not found":
                desc = f"{desc}\n\n{ghost.get('description', '')}".strip()
                specs = ghost.get("specifications", {})
        elif word_count < 50 and specs:
            generated = draft_missing_description(specs, title)
            desc = f"{desc}\n\n{generated}".strip()

        target_schema = determine_schema(cat_string, schemas)
        search_specs = extract_search_specs(title, desc, specs, target_schema)

        embed_text = f"Title: {title}\nDescription: {desc}\nSpecs: {_json.dumps(specs)}"
        embedding = sync_generate_vector(embed_text)

        return desc, specs, search_specs, embedding

    long_desc, display_specs, search_specs, embedding = await asyncio.to_thread(run_enrichment)

    # --- Persist enriched data ---
    try:
        cur.execute(
            """
            UPDATE products SET
                long_description = %s,
                description = %s,
                display_specs = %s::jsonb,
                search_specs = %s::jsonb,
                embedding = %s::vector
            WHERE id = %s
            """,
            (
                long_desc,
                long_desc,
                _json.dumps(display_specs),
                _json.dumps(search_specs),
                embedding,
                product_id,
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"DB write error: {e}")
    finally:
        cur.close()
        conn.close()

    return {
        "message": "Product enriched successfully",
        "product_id": product_id,
        "title": title,
        "long_description_words": len(long_desc.split()),
        "search_specs_keys": list(search_specs.keys()),
    }


# ---------------------------------------------------------------------------
# GET /api/admin/products/{product_id}/history — price + availability history
# ---------------------------------------------------------------------------
@router.get("/products/{product_id}/history", dependencies=[Depends(require_admin)])
def get_product_history(product_id: int):
    """Returns the full change history for a product."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT url FROM products WHERE id = %s", (product_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")

    cur.execute(
        """
        SELECT action, old_price, new_price, changed_at
        FROM product_history
        WHERE url = %s
        ORDER BY changed_at DESC
        LIMIT 50
        """,
        (row["url"],),
    )
    history = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    return {"product_id": product_id, "history": history}


# ---------------------------------------------------------------------------
# POST /api/admin/upload-image — local image upload for Rich Text Editor
# ---------------------------------------------------------------------------
@router.post("/upload-image", dependencies=[Depends(require_admin)])
async def upload_image(file: UploadFile = File(...)):
    """Receives a pasted/uploaded image in the admin dashboard and saves it to static/uploads/"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image")

    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join("static", "uploads", filename)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    url = f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/static/uploads/{filename}"

    # Insert into media_gallery
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO media_gallery (filename, filepath, url) VALUES (%s, %s, %s) RETURNING id",
            (file.filename, filepath, url)
        )
        media_id = cur.fetchone()["id"]
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error saving media: {e}")
    finally:
        cur.close()
        conn.close()

    # Return the absolute URL Assuming frontend makes request to same domain or VITE_API_URL
    return {"id": media_id, "url": url}

# ---------------------------------------------------------------------------
# GET /api/admin/media — fetch media gallery
# ---------------------------------------------------------------------------
@router.get("/media", dependencies=[Depends(require_admin)])
def get_media_gallery():
    """Returns all uploaded images in descending order."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, filename, filepath, url, created_at FROM media_gallery ORDER BY created_at DESC")
        items = [dict(r) for r in cur.fetchall()]
        return {"media": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        cur.close()
        conn.close()
