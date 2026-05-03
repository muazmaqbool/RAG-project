import { useCallback, useEffect, useRef } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { ProductCard } from "@/components/catalog/ProductCard";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowRight } from "lucide-react";
import { Link } from "@tanstack/react-router";

interface Props {
  category: string;
  title: string;
}

const PAGE_SIZE = 12;

export function ProductLane({ category, title }: Props) {
  const sentinel = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, isError } =
    useInfiniteQuery({
      queryKey: ["product-lane", category],
      queryFn: ({ pageParam = 0 }) =>
        api.products.list({
          page: pageParam as number,
          limit: PAGE_SIZE,
          category,
        }),
      initialPageParam: 0,
      getNextPageParam: (lastPage) => {
        const nextPage = lastPage.page + 1;
        return nextPage < lastPage.pages ? nextPage : undefined;
      },
    });

  const allProducts = data?.pages.flatMap((p) => p.results) ?? [];

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
      { rootMargin: "0px 300px 0px 0px", root: scrollContainerRef.current }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMore]);

  if (isError) {
    return null; // Handle error gracefully by not showing the lane
  }

  if (!isLoading && allProducts.length === 0) {
    return null;
  }

  return (
    <section className="w-full px-4 lg:px-8 pb-12">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-foreground">{title}</h2>
        <Link 
          to="/" 
          search={{ category }}
          className="text-sm font-medium text-[#1a73e8] hover:underline flex items-center gap-1"
        >
          View All <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      <div 
        ref={scrollContainerRef}
        className="flex gap-4 overflow-x-auto pb-6 -mx-4 px-4 lg:-mx-8 lg:px-8 snap-x scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent hover:scrollbar-thumb-muted-foreground/40"
      >
        {isLoading ? (
          <>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="min-w-[280px] w-[280px] shrink-0 snap-start">
                <Skeleton className="h-[400px] w-full rounded-xl" />
              </div>
            ))}
          </>
        ) : (
          <>
            {allProducts.map((product) => (
              <div key={product.id} className="min-w-[280px] w-[280px] shrink-0 snap-start">
                <ProductCard product={product} />
              </div>
            ))}
            
            {/* Loading indicator for next page / Sentinel */}
            <div ref={sentinel} className="min-w-[10px] w-[10px] shrink-0 h-full flex items-center justify-center">
              {isFetchingNextPage && (
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#1a73e8]" />
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
