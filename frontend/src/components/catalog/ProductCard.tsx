import { Link } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import type { ProductSummary } from "@/services/api";
import { Badge } from "@/components/ui/badge";
import { useCompare } from "@/hooks/use-compare";

interface Props {
  product: ProductSummary;
}

const FALLBACK_IMAGE =
  "https://images.unsplash.com/photo-1625842268584-8f3296236761?w=600&h=450&fit=crop";

export function ProductCard({ product }: Props) {
  const { addToCompare, removeFromCompare, isInCompare } = useCompare();
  const inCompare = isInCompare(product.id);

  const images = Array.from(
    new Set([product.image_url ?? FALLBACK_IMAGE, ...(product.image_urls || [])])
  ).filter(Boolean);

  const [currentIdx, setCurrentIdx] = useState(0);

  useEffect(() => {
    if (images.length <= 1) return;
    const timer = setInterval(() => {
      setCurrentIdx((prev) => (prev + 1) % images.length);
    }, 5000);
    return () => clearInterval(timer);
  }, [images.length]);

  return (
    <article className="product-card">
      {/* Out of stock overlay */}
      {!product.is_available && (
        <div className="product-card-oos-overlay">
          <Badge variant="destructive">Out of Stock</Badge>
        </div>
      )}

      {/* Category label */}
      {product.leaf_category && (
        <div className="product-card-category">
          {product.leaf_category.toUpperCase()}
        </div>
      )}

      {/* Savings badge */}
      {product.original_price_pkr && product.price_pkr && product.original_price_pkr > product.price_pkr && (
        <div className="absolute top-2 right-2 z-10 bg-red-500 text-white text-xs font-bold px-2 py-1 rounded">
          You Save ₨{(product.original_price_pkr - product.price_pkr).toLocaleString()}
        </div>
      )}

      {/* Image */}
      <Link to="/products/$productId" params={{ productId: String(product.id) }} className="block">
        <div className="product-card-image-wrap">
          {images.map((src, idx) => (
            <img
              key={idx}
              src={src}
              alt={product.title}
              loading="lazy"
              className={`product-card-image ${idx === currentIdx ? "product-card-image--active" : "product-card-image--hidden"}`}
              onError={(e) => {
                (e.target as HTMLImageElement).src = FALLBACK_IMAGE;
              }}
            />
          ))}
          {images.length > 1 && (
            <div className="product-card-dots">
              {images.map((_, idx) => (
                <div
                  key={idx}
                  className={`product-card-dot ${idx === currentIdx ? "product-card-dot--active" : ""}`}
                />
              ))}
            </div>
          )}
        </div>
      </Link>

      {/* Info */}
      <div className="product-card-body">
        <Link to="/products/$productId" params={{ productId: String(product.id) }}>
          <h3 className="product-card-title">
            {product.title}
          </h3>
        </Link>

        {/* Price */}
        <div className="product-card-price-row">
          {product.is_call_for_price || product.price_pkr === null ? (
            <Badge variant="outline" className="text-xs">Call for Price</Badge>
          ) : (
            <div className="flex flex-col gap-0.5">
              {product.original_price_pkr && product.original_price_pkr > product.price_pkr && (
                <span className="text-xs text-muted-foreground line-through">
                  ₨{product.original_price_pkr.toLocaleString()}
                </span>
              )}
              <span className="product-card-price">
                ₨{product.price_pkr.toLocaleString()}
              </span>
            </div>
          )}
        </div>

        {/* Compare toggle */}
        <button
          onClick={() => inCompare ? removeFromCompare(product.id) : addToCompare(product.id)}
          className={`product-card-compare ${inCompare ? "product-card-compare--active" : ""}`}
        >
          {inCompare ? "✓ In Compare" : "+ Add to Compare"}
        </button>
      </div>
    </article>
  );
}
