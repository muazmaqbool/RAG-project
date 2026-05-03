/**
 * Centralized API client.
 * All fetch calls go through here so the base URL and auth headers
 * are managed in one place.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Admin key stored in sessionStorage after login
function getAdminKey(): string | null {
  return sessionStorage.getItem("admin_key");
}

export function setAdminKey(key: string) {
  sessionStorage.setItem("admin_key", key);
}

export function clearAdminKey() {
  sessionStorage.removeItem("admin_key");
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------
async function request<T>(
  path: string,
  options: RequestInit = {},
  admin = false,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (admin) {
    const key = getAdminKey();
    if (key) headers["X-Admin-Key"] = key;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? `HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Type definitions mirroring the backend response models
// ---------------------------------------------------------------------------
export interface ProductSummary {
  id: number;
  url: string;
  title: string;
  is_available: boolean;
  price_pkr: number | null;
  original_price_pkr: number | null;
  is_call_for_price: boolean;
  is_featured: boolean;
  image_url: string | null;
  image_urls: string[] | null;
  leaf_category: string | null;
  categories: string[] | null;
  short_description: string | null;
}

export interface ProductDetail extends ProductSummary {
  long_description: string | null;
  search_specs: Record<string, string> | null;
  display_specs: Record<string, string> | null;
}

export interface ProductListResponse {
  total: number;
  page: number;
  limit: number;
  pages: number;
  results: ProductSummary[];
}

export interface CategoryTree {
  name: string;
  subcategories: string[];
}

export interface CompareResponse {
  products: ProductDetail[];
  spec_keys: string[];
}

export interface SearchResult {
  title: string;
  url: string;
  image_url: string | null;
  price: number | null;
  description: string;
  display_specs: Record<string, string>;
  search_specs: Record<string, string>;
  match_score: number;
  matched_intent: string;
  is_exact_match: boolean;
  ai_selected?: boolean;
}

export interface RecommendResponse {
  explanation: string;
  top_picks: SearchResult[];
  alternatives: SearchResult[];
}

// ---------------------------------------------------------------------------
// Filter options type
// ---------------------------------------------------------------------------
export interface FilterOptions {
  min_price: number;
  max_price: number;
  brands: string[];
  processors: string[];
  rams: string[];
}

// ---------------------------------------------------------------------------
// Public catalog API
// ---------------------------------------------------------------------------
export const api = {
  products: {
    list(params: {
      page?: number;
      limit?: number;
      category?: string;
      subcategory?: string;
      search?: string;
      available_only?: boolean;
      min_price?: number;
      max_price?: number;
      brand?: string;
      processor?: string;
      ram?: string;
    }): Promise<ProductListResponse> {
      const qs = new URLSearchParams();
      if (params.page !== undefined) qs.set("page", String(params.page));
      if (params.limit !== undefined) qs.set("limit", String(params.limit));
      if (params.category) qs.set("category", params.category);
      if (params.subcategory) qs.set("subcategory", params.subcategory);
      if (params.search) qs.set("search", params.search);
      if (params.available_only !== undefined) qs.set("available_only", String(params.available_only));
      if (params.min_price !== undefined) qs.set("min_price", String(params.min_price));
      if (params.max_price !== undefined) qs.set("max_price", String(params.max_price));
      if (params.brand) qs.set("brand", params.brand);
      if (params.processor) qs.set("processor", params.processor);
      if (params.ram) qs.set("ram", params.ram);
      return request(`/api/products?${qs}`);
    },

    filterOptions(): Promise<FilterOptions> {
      return request("/api/products/filter-options");
    },

    featuredProducts(limit = 12): Promise<{ results: ProductSummary[]; total: number }> {
      return request(`/api/products/featured?limit=${limit}`);
    },

    get(id: number): Promise<ProductDetail> {
      return request(`/api/products/${id}`);
    },

    compare(ids: number[]): Promise<CompareResponse> {
      return request(`/api/products/compare?ids=${ids.join(",")}`);
    },

    categories(): Promise<CategoryTree[]> {
      return request("/api/products/categories/tree");
    },
  },

  search: {
    semantic(query: string, minPrice?: number, maxPrice?: number): Promise<{ query: string; results: SearchResult[] }> {
      return request("/search", {
        method: "POST",
        body: JSON.stringify({ query, min_price: minPrice ?? null, max_price: maxPrice ?? null, top_k: 10 }),
      });
    },

    recommend(query: string): Promise<RecommendResponse> {
      return request("/recommend", {
        method: "POST",
        body: JSON.stringify({ query, top_k: 10 }),
      });
    },
  },

  admin: {
    create(product: Partial<ProductDetail>): Promise<{ id: number; message: string }> {
      return request("/api/admin/products", { method: "POST", body: JSON.stringify(product) }, true);
    },

    update(id: number, updates: Partial<ProductDetail>): Promise<{ message: string }> {
      return request(`/api/admin/products/${id}`, { method: "PUT", body: JSON.stringify(updates) }, true);
    },

    delete(id: number): Promise<{ message: string }> {
      return request(`/api/admin/products/${id}`, { method: "DELETE" }, true);
    },

    enrich(id: number): Promise<{ message: string; title: string; search_specs_keys: string[] }> {
      return request(`/api/admin/products/${id}/enrich`, { method: "POST" }, true);
    },

    history(id: number): Promise<{ product_id: number; history: Array<{ action: string; old_price: number | null; new_price: number | null; changed_at: string }> }> {
      return request(`/api/admin/products/${id}/history`, {}, true);
    },

    toggleFeatured(id: number): Promise<{ id: number; is_featured: boolean }> {
      return request(`/api/admin/products/${id}/toggle-featured`, { method: "PATCH" }, true);
    },

    uploadImage(file: File): Promise<{ url: string }> {
      const formData = new FormData();
      formData.append("file", file);
      
      const key = getAdminKey();
      const headers: Record<string, string> = key ? { "X-Admin-Key": key } : {};

      // Need to bypass the default JSON headers from `request` so fetch automatically sets the multipart boundary.
      return fetch(`${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api/admin/upload-image`, {
        method: "POST",
        body: formData,
        headers,
      }).then(async (res) => {
        if (!res.ok) throw new Error("Image upload failed");
        return res.json();
      });
    },
  },
};
