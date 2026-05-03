/**
 * Product service — thin re-export layer.
 * All actual data fetching now goes through api.ts → FastAPI backend.
 * The mock data is intentionally removed.
 *
 * Components should call these functions (or use api.ts directly with TanStack Query).
 */

export type { ProductSummary, ProductDetail, ProductListResponse } from "@/services/api";
export { api } from "@/services/api";
