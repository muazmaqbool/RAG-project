import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Navbar } from "@/components/layout/Navbar";
import { CategorySidebar, CategoryPills } from "@/components/catalog/CategorySidebar";
import { ProductGrid } from "@/components/catalog/ProductGrid";
import { ProductCard } from "@/components/catalog/ProductCard";
import { FilterPanel, type FilterState } from "@/components/catalog/FilterPanel";
import { AiSearchPanel } from "@/components/catalog/AiSearchPanel";
import { CompareBar } from "@/components/catalog/CompareBar";
import { ProductLane } from "@/components/catalog/ProductLane";
import { Sheet, SheetContent, SheetTrigger, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Filter } from "lucide-react";

type IndexSearch = {
  category?: string;
  subcategory?: string;
};

export const Route = createFileRoute("/")({
  validateSearch: (search: Record<string, unknown>): IndexSearch => {
    return {
      category: typeof search.category === "string" ? search.category : undefined,
      subcategory: typeof search.subcategory === "string" ? search.subcategory : undefined,
    };
  },
  component: Index,
  head: () => ({
    meta: [
      { title: "Laptops, Accessories & Electronics in Lahore — Al-Aqsa Computers" },
      {
        name: "description",
        content:
          "Best prices on laptops, accessories, smart gadgets and top brands in Lahore, Pakistan. Shop new & used laptops from HP, Dell, Lenovo, Apple at Al-Aqsa Computers.",
      },
      { property: "og:title", content: "Al-Aqsa Computers — Electronics & Laptops Lahore" },
      {
        property: "og:description",
        content: "Best prices on laptops and electronics in Lahore, Pakistan.",
      },
      { name: "keywords", content: "laptops lahore, best laptop price lahore, electronics pakistan, used laptops lahore, al aqsa computers" },
    ],
  }),
});

const INITIAL_FILTERS: FilterState = {
  minPrice: undefined,
  maxPrice: undefined,
  brand: "",
  processor: "",
  ram: "",
};

// Icons for feature strip
function ShieldIcon() {
  return (
    <svg className="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function TagIcon() {
  return (
    <svg className="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
      <line x1="7" y1="7" x2="7.01" y2="7" />
    </svg>
  );
}
function HeadsetIcon() {
  return (
    <svg className="feature-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 18v-6a9 9 0 0 1 18 0v6" />
      <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z" />
    </svg>
  );
}
function MapPinIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}
function PhoneIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.71 3.37 2 2 0 0 1 3.69 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.1a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
    </svg>
  );
}

const SLIDER_IMAGES = [
  "https://alaqsa.com.pk/wp-content/uploads/2025/09/maxresdefault.jpg",
  "https://alaqsa.com.pk/wp-content/uploads/2025/09/maxresdefault-1.jpg",
  "https://alaqsa.com.pk/wp-content/uploads/2025/09/maxresdefault-2.jpg",
  "https://alaqsa.com.pk/wp-content/uploads/2025/09/maxresdefault-3.jpg",
];

function Index() {
  const { category: urlCategory, subcategory: urlSubcategory } = Route.useSearch();
  const navigate = useNavigate({ from: "/" });
  
  const category = urlCategory || "All";
  const [subcategory, setSubcategory] = useState(urlSubcategory || "");
  const [search, setSearch] = useState("");
  const [aiActive, setAiActive] = useState(false);
  const [filters, setFilters] = useState<FilterState>(INITIAL_FILTERS);
  const [currentSlide, setCurrentSlide] = useState(0);

  // Sync state with URL and reset filters when returning home
  useEffect(() => {
    setSubcategory(urlSubcategory || "");
    if (!urlCategory && !urlSubcategory) {
      setFilters(INITIAL_FILTERS);
      setSearch("");
      setAiActive(false);
    }
  }, [urlCategory, urlSubcategory]);

  // Auto-scroll slider
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % SLIDER_IMAGES.length);
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  // Fetch featured products
  const { data: featuredData } = useQuery({
    queryKey: ["featured-products"],
    queryFn: () => api.products.featuredProducts(6),
  });

  const handleCategorySelect = (cat: string, sub: string) => {
    navigate({
      search: {
        category: cat !== "All" ? cat : undefined,
        subcategory: sub ? sub : undefined,
      },
    });
    setSubcategory(sub);
    setAiActive(false);
  };

  const h1Text =
    subcategory
      ? subcategory
      : category !== "All"
        ? category
        : "Electronics & Laptops Catalog";

  const isHome = category === "All" && !subcategory && !search && !aiActive && JSON.stringify(filters) === JSON.stringify(INITIAL_FILTERS);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar
        search={search}
        onSearch={(q) => { setSearch(q); setAiActive(false); }}
        aiActive={aiActive}
        onAiToggle={() => setAiActive((v) => !v)}
      />

      {isHome ? (
        <div className="flex-1 pb-16">
          {/* ── Top Section (Slider & Map) ─────────────────────────────────── */}
          <section className="w-full px-4 lg:px-8 py-8">
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
              {/* Left: Featured Slider */}
              <div className="lg:col-span-3 rounded-xl overflow-hidden shadow-sm relative group aspect-video bg-black">
                {SLIDER_IMAGES.map((img, idx) => (
                  <img 
                    key={idx}
                    src={img} 
                    alt={`Promotional Banner ${idx + 1}`} 
                    className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-1000 ${
                      idx === currentSlide ? "opacity-100" : "opacity-0"
                    }`}
                  />
                ))}
                
                {/* Dots */}
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 z-10">
                  {SLIDER_IMAGES.map((_, idx) => (
                    <button
                      key={idx}
                      onClick={() => setCurrentSlide(idx)}
                      className={`w-2.5 h-2.5 rounded-full transition-all ${
                        idx === currentSlide ? "bg-white scale-125" : "bg-white/50 hover:bg-white/80"
                      }`}
                      aria-label={`Go to slide ${idx + 1}`}
                    />
                  ))}
                </div>
              </div>

              {/* Right: Map & Location */}
              <div className="lg:col-span-1 bg-white rounded-xl shadow-sm border border-border p-4 flex flex-col h-full">
                 <div className="flex-1 rounded-lg overflow-hidden relative">
                   <iframe
                     title="Al-Aqsa Computers location on Google Maps"
                     src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3402.6155849836014!2d74.30977507624658!3d31.557506141419537!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x391904c868e8c6a9%3A0xa3e98e3bc1a89c7f!2sAl-Aqsa%20Computers!5e0!3m2!1sen!2spk!4v1714000000000!5m2!1sen!2spk"
                     width="100%"
                     height="100%"
                     style={{ border: 0 }}
                     allowFullScreen
                     loading="lazy"
                     referrerPolicy="no-referrer-when-downgrade"
                     className="absolute inset-0"
                   />
                   <a 
                     href="https://maps.google.com" 
                     target="_blank" 
                     rel="noreferrer"
                     className="absolute top-2 left-2 bg-white/90 text-blue-600 text-xs font-bold px-3 py-1.5 rounded shadow hover:bg-white transition-colors"
                   >
                     Open in Maps ↗
                   </a>
                 </div>
              </div>
            </div>
          </section>

          {/* ── Category Lanes ───────────────────────────────────────────── */}
          <ProductLane category="New Laptops" title="New Laptops" />
          <ProductLane category="Used Laptops" title="Used Laptops" />

          {/* ── Featured Products ────────────────────────────────────────── */}
          {featuredData && featuredData.results.length > 0 && (
            <section className="w-full px-4 lg:px-8 pb-8">
              <h2 className="text-2xl font-bold text-foreground mb-6">Featured Products</h2>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4">
                {featuredData.results.slice(0, 6).map((p) => (
                  <ProductCard key={p.id} product={p} />
                ))}
              </div>
            </section>
          )}
        </div>
      ) : (
        /* ── Catalog Section ──────────────────────────────────────────── */
        <div id="catalog" className="flex-1 w-full flex flex-col min-h-screen">
          {/* Mobile category pills */}
          <CategoryPills
            selectedCategory={category}
            selectedSubcategory={subcategory}
            onSelect={handleCategorySelect}
          />

          <div className="w-full px-4 lg:px-8 py-8 flex flex-1 flex-col lg:flex-row gap-8">
            <main className="flex-1 min-w-0 flex flex-col h-full">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 shrink-0">
                <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
                  <Sheet>
                    <SheetTrigger asChild>
                      <button className="flex items-center gap-2 text-sm font-medium border border-border px-3 py-1.5 rounded-md hover:bg-muted transition-colors">
                        <Filter className="h-4 w-4" />
                        Filters
                      </button>
                    </SheetTrigger>
                    <SheetContent side="left" className="w-[300px] sm:w-[400px] overflow-y-auto">
                      <SheetHeader className="mb-6">
                        <SheetTitle>Filters</SheetTitle>
                      </SheetHeader>
                      <div className="flex flex-col gap-8">
                        <CategorySidebar
                          selectedCategory={category}
                          selectedSubcategory={subcategory}
                          onSelect={handleCategorySelect}
                        />
                        <FilterPanel filters={filters} onChange={setFilters} />
                      </div>
                    </SheetContent>
                  </Sheet>
                  {aiActive ? "AI Catalog Search" : h1Text}
                </h1>
              </div>

              {aiActive ? (
                <div className="flex-1">
                  <AiSearchPanel onClose={() => setAiActive(false)} />
                </div>
              ) : (
                <div className="flex-1 pb-8">
                  <ProductGrid
                    category={category}
                    subcategory={subcategory}
                    search={search}
                    filters={filters}
                  />
                </div>
              )}
            </main>
          </div>
        </div>
      )}
    </div>
  );
}
