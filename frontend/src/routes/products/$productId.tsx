import { createFileRoute, Link } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/services/api';
import { Navbar } from '@/components/layout/Navbar';
import { SpecsTable } from '@/components/catalog/SpecsTable';
import { useCompare } from '@/hooks/use-compare';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ChevronRight, ArrowLeft } from 'lucide-react';

export const Route = createFileRoute('/products/$productId')({
  component: ProductDetailPage,
});

const FALLBACK_IMAGE =
  'https://images.unsplash.com/photo-1625842268584-8f3296236761?w=600&h=600&fit=crop';

function ProductDetailPage() {
  const { productId } = Route.useParams();
  const { addToCompare, removeFromCompare, isInCompare } = useCompare();
  const [activeImg, setActiveImg] = useState(0);

  const { data: product, isLoading, isError } = useQuery({
    queryKey: ['product', productId],
    queryFn: () => api.products.get(Number(productId)),
  });

  const inCompare = product ? isInCompare(product.id) : false;

  if (isLoading) {
    return (
      <div className='min-h-screen bg-background'>
        <Navbar search="" onSearch={() => {}} aiActive={false} onAiToggle={() => {}} />
        <div className='w-full px-4 lg:px-8 py-8'>
          <div className='grid grid-cols-1 gap-8 lg:grid-cols-2'>
            <Skeleton className='aspect-square w-full rounded-xl' />
            <div className='space-y-4'>
              <Skeleton className='h-8 w-3/4' />
              <Skeleton className='h-6 w-1/3' />
              <Skeleton className='h-40 w-full' />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (isError || !product) {
    return (
      <div className='py-20 text-center'>
        <p className='text-lg font-medium text-destructive'>Product not found.</p>
        <Link to='/' className='mt-4 inline-block text-sm text-primary hover:underline'>
          ← Back to catalog
        </Link>
      </div>
    );
  }

  // Build image gallery
  const images = Array.from(
    new Set([product.image_url ?? FALLBACK_IMAGE, ...(product.image_urls || [])])
  ).filter(Boolean);

  // Build short description bullets from the short_description field
  const bullets = product.short_description
    ? product.short_description
        .split('\n')
        .map((b) => b.replace(/^[-•*]\t*/, '').trim())
        .filter(Boolean)
    : [];

  const breadcrumbParts = product.leaf_category?.split('>').map((p) => p.trim()) ?? [];

  return (
    <div className='min-h-screen bg-background pb-20'>
      {/* Full Navbar on PDP */}
      <Navbar search="" onSearch={() => {}} aiActive={false} onAiToggle={() => {}} />

      {/* Breadcrumb */}
      <nav
        aria-label='Breadcrumb'
        className='border-b border-border bg-muted/30 px-4 py-2 text-xs text-muted-foreground lg:px-8'
      >
        <ol className='w-full flex flex-wrap items-center gap-1'>
          <li>
            <Link to='/' className='hover:text-foreground transition-colors'>
              Home
            </Link>
          </li>
          {breadcrumbParts.map((part, i) => (
            <li key={i} className='flex items-center gap-1'>
              <ChevronRight className='h-3 w-3' />
              {i < breadcrumbParts.length - 1 ? (
                <Link
                  to='/'
                  search={{ category: part }}
                  className='hover:text-foreground transition-colors'
                >
                  {part}
                </Link>
              ) : (
                <span className='text-foreground font-medium'>{part}</span>
              )}
            </li>
          ))}
        </ol>
      </nav>

      <div className='w-full px-4 py-6 lg:px-8'>
        {/* Back button */}
        <Link
          to='/'
          className='mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors'
        >
          <ArrowLeft className='h-4 w-4' />
          Back to catalog
        </Link>

        {/* Hero grid */}
        <div className='grid grid-cols-1 gap-8 lg:grid-cols-2'>
          {/* Image gallery */}
          <div className='pdp-gallery'>
            {/* Main image */}
            <div className='pdp-main-image-wrap'>
              <img
                src={images[activeImg] ?? FALLBACK_IMAGE}
                alt={product.title}
                className='pdp-main-image'
                onError={(e) => {
                  (e.target as HTMLImageElement).src = FALLBACK_IMAGE;
                }}
              />
            </div>

            {/* Thumbnail strip — only shown when multiple images */}
            {images.length > 1 && (
              <div className='pdp-thumbnails' role='list' aria-label='Product image thumbnails'>
                {images.map((src, idx) => (
                  <button
                    key={idx}
                    onClick={() => setActiveImg(idx)}
                    className={`pdp-thumb ${idx === activeImg ? 'pdp-thumb--active' : ''}`}
                    aria-label={`View image ${idx + 1}`}
                    aria-pressed={idx === activeImg}
                  >
                    <img
                      src={src}
                      alt={`${product.title} thumbnail ${idx + 1}`}
                      className='pdp-thumb-img'
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = FALLBACK_IMAGE;
                      }}
                    />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Product info */}
          <div className='flex flex-col gap-5'>
            {/* Category */}
            {product.leaf_category && (
              <p className='text-sm font-medium uppercase tracking-wider text-muted-foreground'>
                {product.leaf_category}
              </p>
            )}

            {/* Title — h1 for SEO */}
            <h1 className='text-3xl font-bold leading-tight text-primary mb-4'>
              {product.title}
            </h1>

            {/* Price & Stock */}
            <div className='flex flex-col gap-2 mb-4'>
              <div className='flex items-end gap-3'>
                {product.is_call_for_price || product.price_pkr === null ? (
                  <Badge variant='outline' className='text-base'>Call for Price</Badge>
                ) : (
                  <>
                    {product.original_price_pkr && (
                      <span className='text-lg text-muted-foreground line-through decoration-1'>
                        Rs {product.original_price_pkr.toLocaleString()}
                      </span>
                    )}
                    <span className='text-3xl font-bold text-[#1a73e8]'>
                      Rs {product.price_pkr.toLocaleString()}
                    </span>
                  </>
                )}
              </div>
              
              <div className='mt-2 space-y-1'>
                {product.is_available ? (
                  <span className='inline-block rounded bg-green-500 px-2 py-0.5 text-xs font-semibold text-white'>
                    In stock
                  </span>
                ) : (
                  <span className='inline-block rounded bg-red-500 px-2 py-0.5 text-xs font-semibold text-white'>
                    Out of stock
                  </span>
                )}
                {product.is_available && (
                  <p className='text-sm text-muted-foreground'>
                    {Math.floor(Math.random() * 15 + 5)} people are viewing this right now
                  </p>
                )}
              </div>
            </div>

            {/* Short description — bullet list */}
            {bullets.length > 0 && (
              <ul className='space-y-1.5 border-t border-border pt-4'>
                {bullets.map((b, i) => (
                  <li key={i} className='flex items-start gap-2 text-sm text-foreground'>
                    <span className='mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary' />
                    {b}
                  </li>
                ))}
              </ul>
            )}

            {/* Actions (Quantity, Cart, Compare, WhatsApp) */}
            <div className='mt-6 space-y-4 border-t border-border pt-6'>
              <div className='flex items-center gap-4'>
                <div className='flex items-center gap-2'>
                  <span className='text-sm font-medium'>Quantity:</span>
                  <input 
                    type='number' 
                    min='1' 
                    defaultValue='1' 
                    className='w-16 rounded border border-border px-2 py-1.5 text-center focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary'
                  />
                </div>
                <button
                  className='flex-1 rounded-full border-2 border-[#1a73e8] px-4 py-2 text-sm font-semibold text-[#1a73e8] transition-colors hover:bg-[#1a73e8] hover:text-white'
                >
                  ADD TO CART
                </button>
              </div>

              <div className='flex gap-3'>
                <button
                  onClick={() =>
                    inCompare ? removeFromCompare(product.id) : addToCompare(product.id)
                  }
                  className={`flex-1 rounded-full px-4 py-2.5 text-xs font-bold transition-colors flex items-center justify-center gap-2 ${
                    inCompare
                      ? 'border-2 border-[#1a73e8] bg-[#1a73e8]/10 text-[#1a73e8]'
                      : 'bg-[#1a73e8] text-white hover:bg-[#0d5cbf]'
                  }`}
                >
                  {inCompare ? '✓ ADDED TO COMPARE' : '⚖ ADD TO COMPARE'}
                </button>
                <a
                  href={`https://wa.me/923367120011?text=Hello,%20I%20am%20interested%20in%20ordering%20${encodeURIComponent(product.title)}%20(${window.location.href})`}
                  target='_blank'
                  rel='noopener noreferrer'
                  className='flex-1 rounded-full bg-[#25D366] px-4 py-2.5 text-xs font-bold text-white transition-colors hover:bg-[#20bd5a] flex items-center justify-center gap-2'
                >
                  <svg width='16' height='16' viewBox='0 0 24 24' fill='currentColor'><path d='M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z'/><path d='M12 0C5.374 0 0 5.373 0 12c0 2.117.554 4.133 1.521 5.872L.057 23.98l6.304-1.654A11.935 11.935 0 0 0 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.816 9.816 0 0 1-5.001-1.371l-.359-.214-3.717.975.993-3.618-.235-.372A9.817 9.817 0 0 1 2.182 12C2.182 6.574 6.574 2.182 12 2.182S21.818 6.574 21.818 12 17.426 21.818 12 21.818z'/></svg>
                  ORDER ON WHATSAPP
                </a>
              </div>
            </div>

            {/* Specs — collapsible, right below product info */}
            {product.display_specs && Object.keys(product.display_specs).length > 0 && (
              <div className='mt-2'>
                <SpecsTable specs={product.display_specs} />
              </div>
            )}
          </div>
        </div>

        {/* Long description */}
        {product.long_description && (
          <div className='mt-10'>
            <h2 className='mb-4 text-lg font-bold text-foreground border-b border-border pb-2'>
              About this product
            </h2>
            <div
              className='product-description-content'
              dangerouslySetInnerHTML={{ __html: product.long_description }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
