"""
Public catalog API endpoints.
All routes are read-only and require no authentication.
"""
import os
from typing import Optional
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/products", tags=["products"])

# ---------------------------------------------------------------------------
# Hardcoded category tree derived from the website's URL structure.
# This reflects the real parent → subcategory hierarchy of alaqsa.com.pk.
# ---------------------------------------------------------------------------
CATEGORY_TREE = [
    {
        "name": "New Laptops",
        "subcategories": ["Lenovo", "HP", "Gaming & Workstations", "Dell"],
    },
    {
        "name": "Used Laptops",
        "subcategories": [
            "HP", "Toshiba", "Lenovo", "Mix Brands",
            "Asus", "Gaming & Workstations", "Dell", "Apple",
        ],
    },
    {
        "name": "Accessories",
        "subcategories": [
            "Chargers", "Batteries", "SSD", "Speakers & Headphones",
            "External Enclosures", "Laptop Stands & Cooling Pads",
            "Hubs & Convertors", "Keyboards & Mouse",
            "Mobile Accessories", "Laptop Bags", "Softwares",
        ],
    },
    {
        "name": "Smart Gadgets",
        "subcategories": ["Android BOX & Screen Mirror", "Gaming Stick", "Graphic Tablets"],
    },
    {
        "name": "Top Brands",
        "subcategories": ["Apple", "Earldom", "UGREEN", "Amaze", "Baseus", "MI (Xiaomi)"],
    },
]


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
# Response models
# ---------------------------------------------------------------------------
class ProductSummary(BaseModel):
    id: int
    url: str
    title: str
    is_available: bool
    price_pkr: Optional[int]
    original_price_pkr: Optional[int] = None
    is_call_for_price: bool
    is_featured: bool = False
    image_url: Optional[str]
    image_urls: Optional[list] = None
    leaf_category: Optional[str]
    categories: Optional[list]
    short_description: Optional[str]

    class Config:
        from_attributes = True


class ProductDetail(BaseModel):
    id: int
    url: str
    title: str
    is_available: bool
    price_pkr: Optional[int]
    original_price_pkr: Optional[int] = None
    is_call_for_price: bool
    is_featured: bool = False
    image_url: Optional[str]
    image_urls: Optional[list] = None
    leaf_category: Optional[str]
    categories: Optional[list]
    short_description: Optional[str]
    long_description: Optional[str]
    search_specs: Optional[dict]
    display_specs: Optional[dict]

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# GET /api/products — paginated, filtered product list
# ---------------------------------------------------------------------------
@router.get("", response_model=dict)
def list_products(
    page: int = Query(0, ge=0, description="Zero-based page index"),
    limit: int = Query(24, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Parent category name (e.g. 'New Laptops')"),
    subcategory: Optional[str] = Query(None, description="Subcategory name (e.g. 'HP')"),
    search: Optional[str] = Query(None, description="Title keyword search"),
    available_only: bool = Query(True, description="Only return in-stock / available products"),
    featured_only: bool = Query(False, description="Only return featured products"),
    min_price: Optional[int] = Query(None, description="Minimum price in PKR"),
    max_price: Optional[int] = Query(None, description="Maximum price in PKR"),
    brand: Optional[str] = Query(None, description="Brand name filter (matched in search_specs)"),
    processor: Optional[str] = Query(None, description="Processor filter (matched in search_specs)"),
    ram: Optional[str] = Query(None, description="RAM filter (matched in search_specs)"),
):
    """
    Returns a paginated list of products.
    Embeddings and long descriptions are intentionally excluded for performance.
    Supports optional filtering by price range, brand, processor, and RAM.
    """
    conn = get_db()
    cur = conn.cursor()

    conditions = []
    params: list = []

    if available_only:
        conditions.append("is_available = TRUE")

    # Category + subcategory filter against the categories JSON array
    db_cat = "Brands" if category == "Top Brands" else category
    if db_cat and subcategory:
        conditions.append("categories::text ILIKE %s")
        params.append(f'%"{db_cat} > {subcategory}"%')
    elif db_cat:
        # Match elements like "Brands > Apple" or "New Laptops"
        conditions.append("categories::text ILIKE %s")
        params.append(f'%"{db_cat}%')

    if search:
        conditions.append("title ILIKE %s")
        params.append(f"%{search}%")

    if featured_only:
        conditions.append("is_featured = TRUE")

    # Price range filter
    if min_price is not None:
        conditions.append("price_pkr >= %s")
        params.append(min_price)
    if max_price is not None:
        conditions.append("price_pkr <= %s")
        params.append(max_price)

    # Spec-based filters — match against search_specs JSON text
    if brand:
        conditions.append("search_specs::text ILIKE %s")
        params.append(f"%{brand}%")
    if processor:
        conditions.append("search_specs::text ILIKE %s")
        params.append(f"%{processor}%")
    if ram:
        conditions.append("search_specs::text ILIKE %s")
        params.append(f"%{ram}%")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Total count for pagination metadata
    cur.execute(
        f"SELECT COUNT(*) FROM products {where_clause}",
        params,
    )
    total = cur.fetchone()["count"]

    # Fetch page — no embedding, no long_description
    cur.execute(
        f"""
        SELECT id, url, title, is_available, price_pkr, original_price_pkr, is_call_for_price,
               is_featured, image_url, image_urls, leaf_category, categories, short_description
        FROM products
        {where_clause}
        ORDER BY id
        LIMIT %s OFFSET %s
        """,
        params + [limit, page * limit],
    )
    rows = [dict(r) for r in cur.fetchall()]

    cur.close()
    conn.close()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "results": rows,
    }


# ---------------------------------------------------------------------------
# GET /api/products/compare — Fetch multiple products by ID
# Must be declared BEFORE /{product_id} to avoid route shadowing
# ---------------------------------------------------------------------------
@router.get("/compare")
def get_compare_products(ids: str = Query(..., description="Comma-separated product IDs")):
    """
    Returns full details for multiple products side-by-side for comparison.
    """
    id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
    
    if not id_list:
        return []

    conn = get_db()
    cur = conn.cursor()

    # We fetch full details (including specs) since compare needs them
    cur.execute(
        """
        SELECT id, url, title, is_available, price_pkr, original_price_pkr, is_call_for_price,
               image_url, image_urls, leaf_category, display_specs, search_specs
        FROM products
        WHERE id = ANY(%s)
        """,
        (id_list,),
    )
    rows = [dict(r) for r in cur.fetchall()]

    cur.close()
    conn.close()

    # Sort results to match requested order if possible
    rows.sort(key=lambda x: id_list.index(x["id"]) if x["id"] in id_list else 999)

    # Collect all unique spec keys to build the comparison table
    spec_keys_set = set()
    for row in rows:
        specs = row.get("display_specs") or {}
        spec_keys_set.update(specs.keys())

    return {
        "products": rows,
        "spec_keys": sorted(list(spec_keys_set))
    }


# ---------------------------------------------------------------------------
# GET /api/products/filter-options — distinct filter values for UI dropdowns
# Must be declared BEFORE /{product_id} to avoid route shadowing
# ---------------------------------------------------------------------------
@router.get("/filter-options")
def get_filter_options():
    """
    Returns distinct available values for brand, processor, and RAM
    extracted from search_specs, plus the min/max price range.
    Used to populate the frontend filter panel dropdowns.
    """
    conn = get_db()
    cur = conn.cursor()

    # Price range
    cur.execute("SELECT MIN(price_pkr), MAX(price_pkr) FROM products WHERE is_available = TRUE AND price_pkr IS NOT NULL")
    price_row = cur.fetchone()
    min_price = int(price_row["min"]) if price_row["min"] else 0
    max_price = int(price_row["max"]) if price_row["max"] else 500000

    # Extract common spec keys from search_specs JSON — use jsonb operators
    def get_distinct_spec_values(key: str) -> list[str]:
        try:
            cur.execute(
                """
                SELECT DISTINCT search_specs->>%s AS val
                FROM products
                WHERE is_available = TRUE
                  AND search_specs ? %s
                  AND search_specs->>%s IS NOT NULL
                  AND search_specs->>%s != ''
                ORDER BY val
                LIMIT 50
                """,
                (key, key, key, key),
            )
            return [r["val"] for r in cur.fetchall() if r["val"]]
        except Exception:
            return []

    brands = get_distinct_spec_values("Brand")
    processors = get_distinct_spec_values("Processor")
    rams = get_distinct_spec_values("RAM")

    cur.close()
    conn.close()

    return {
        "min_price": min_price,
        "max_price": max_price,
        "brands": brands,
        "processors": processors,
        "rams": rams,
    }


# ---------------------------------------------------------------------------
# GET /api/products/featured — featured products for homepage
# Must be declared BEFORE /{product_id} to avoid route shadowing
# ---------------------------------------------------------------------------
@router.get("/featured")
def get_featured_products(limit: int = Query(12, ge=1, le=50)):
    """Returns products marked as featured, for the homepage showcase."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, url, title, is_available, price_pkr, original_price_pkr,
               is_call_for_price, is_featured, image_url, image_urls,
               leaf_category, categories, short_description
        FROM products
        WHERE is_featured = TRUE AND is_available = TRUE
        ORDER BY id DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"results": rows, "total": len(rows)}


# ---------------------------------------------------------------------------
# GET /api/products/compare — side-by-side spec comparison
# Must be declared BEFORE /{product_id} to avoid route shadowing
# ---------------------------------------------------------------------------
@router.get("/compare")
def compare_products(
    ids: str = Query(..., description="Comma-separated product IDs, e.g. '1,5,12'"),
):
    """Returns full spec data for up to 3 products for comparison view."""
    try:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids must be comma-separated integers")

    if not id_list:
        raise HTTPException(status_code=400, detail="At least one product ID required")
    if len(id_list) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 products can be compared at once")

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, url, title, price_pkr, is_call_for_price, is_available,
               image_url, image_urls, leaf_category, search_specs, display_specs
        FROM products
        WHERE id = ANY(%s)
        """,
        (id_list,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No products found for given IDs")

    # Build a unified set of spec keys across all products for aligned comparison table
    all_keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in (r.get("display_specs") or {}).keys():
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

    return {"products": rows, "spec_keys": all_keys}


# ---------------------------------------------------------------------------
# GET /api/products/{product_id} — full product detail
# ---------------------------------------------------------------------------
@router.get("/{product_id}")
def get_product(product_id: int):
    """Returns the full product record including descriptions and specs. Excludes embedding vector."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, url, title, is_available, price_pkr, original_price_pkr, is_call_for_price,
               is_featured, image_url, image_urls, leaf_category, categories,
               short_description, long_description,
               search_specs, display_specs
        FROM products
        WHERE id = %s
        """,
        (product_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Product not found")

    return dict(row)


# ---------------------------------------------------------------------------
# GET /api/categories — category tree for sidebar/navigation
# ---------------------------------------------------------------------------
@router.get("/categories/tree")
def get_categories():
    """Returns the full nested category tree for sidebar navigation."""
    return CATEGORY_TREE
