import { useCallback, useEffect, useRef } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { ProductCard } from "@/components/catalog/ProductCard";
import { Skeleton } from "@/components/ui/skeleton";
import type { FilterState } from "@/components/catalog/FilterPanel";

interface Props {
  category: string;
  subcategory: string;
  search: string;
  filters?: FilterState;
}

const PAGE_SIZE = 24;

export function ProductGrid({ category, subcategory, search, filters }: Props) {
  const sentinel = useRef<HTMLDivElement>(null);

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } =
    useInfiniteQuery({
      queryKey: ["products", category, subcategory, search, filters],
      queryFn: ({ pageParam = 0 }) =>
        api.products.list({
          page: pageParam as number,
          limit: PAGE_SIZE,
          category: category !== "All" ? category : undefined,
          subcategory: subcategory || undefined,
          search: search || undefined,
          min_price: filters?.minPrice,
          max_price: filters?.maxPrice,
          brand: filters?.brand || undefined,
          processor: filters?.processor || undefined,
          ram: filters?.ram || undefined,
        }),
      initialPageParam: 0,
      getNextPageParam: (lastPage) => {
        const nextPage = lastPage.page + 1;
        return nextPage < lastPage.pages ? nextPage : undefined;
      },
    });

  const allProducts = data?.pages.flatMap((p) => p.results) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  // Observe sentinel DIV — fetch next page when it enters viewport
  const loadMore = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { rootMargin: "300px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMore]);

  if (isError) {
    return (
      <div className="py-16 text-center text-destructive">
        Failed to load products. Make sure the backend is running on{" "}
        <code className="text-xs">{import.meta.env.VITE_API_URL}</code>.
      </div>
    );
  }

  return (
    <section aria-label="Product listing">
      {/* Result count */}
      {!isLoading && (
        <p className="mb-4 text-sm text-muted-foreground">
          {total.toLocaleString()} product{total !== 1 ? "s" : ""} found
        </p>
      )}

      {/* Empty state */}
      {!isLoading && allProducts.length === 0 && (
        <div className="py-20 text-center">
          <p className="text-lg font-medium text-foreground">No products found</p>
          <p className="mt-1 text-sm text-muted-foreground">Try a different category or search term.</p>
        </div>
      )}

      {/* Product grid */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-4">
        {allProducts.map((p) => (
          <ProductCard key={p.id} product={p} />
        ))}

        {/* Skeleton loaders while fetching next page */}
        {(isLoading || isFetchingNextPage) &&
          Array.from({ length: 8 }).map((_, i) => (
            <div
              key={`skel-${i}`}
              className="flex flex-col overflow-hidden rounded-lg border border-border bg-card"
            >
              <Skeleton className="aspect-[4/3] w-full" />
              <div className="space-y-2 p-4">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
                <Skeleton className="mt-2 h-5 w-1/3" />
              </div>
            </div>
          ))}
      </div>

      {/* Invisible sentinel for IntersectionObserver */}
      <div ref={sentinel} className="h-4" />
    </section>
  );
}
