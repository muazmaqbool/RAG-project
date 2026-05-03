import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Navbar } from "@/components/layout/Navbar";
import { useCompare } from "@/hooks/use-compare";
import { ArrowLeft, Trash2, CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/compare")({
  component: ComparePage,
});

function ComparePage() {
  const { ids, removeFromCompare, clearCompare } = useCompare();

  const { data: compareData, isLoading } = useQuery({
    queryKey: ["compare", ids],
    queryFn: () => api.products.compare(ids),
    enabled: ids.length > 0,
  });

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar search="" onSearch={() => {}} aiActive={false} onAiToggle={() => {}} />

      <main className="flex-1 w-full px-4 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to catalog
            </Link>
            <h1 className="text-3xl font-bold text-foreground">Compare Laptops</h1>
          </div>
          
          {ids.length > 0 && (
            <button 
              onClick={clearCompare}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-destructive bg-destructive/10 hover:bg-destructive/20 rounded-md transition-colors"
            >
              <Trash2 className="h-4 w-4" />
              Clear All
            </button>
          )}
        </div>

        {ids.length === 0 ? (
          <div className="text-center py-20 bg-muted/30 rounded-xl border border-border">
            <div className="text-muted-foreground text-lg mb-4">You have no items in your comparison list.</div>
            <Link to="/" className="inline-flex items-center justify-center px-6 py-3 bg-[#1a73e8] text-white rounded-md font-medium hover:bg-[#0d5cbf] transition-colors">
              Browse Catalog
            </Link>
          </div>
        ) : isLoading ? (
          <div className="py-20 text-center text-muted-foreground animate-pulse">
            Loading comparison data...
          </div>
        ) : compareData && compareData.products.length > 0 ? (
          <div className="overflow-x-auto pb-8">
            <table className="w-full border-collapse min-w-[800px]">
              <thead>
                <tr>
                  <th className="p-4 border-b-2 border-border text-left w-48 sticky left-0 bg-background/95 backdrop-blur z-10 font-semibold text-muted-foreground uppercase tracking-wider text-xs">
                    Product
                  </th>
                  {compareData.products.map(p => (
                    <th key={p.id} className="p-4 border-b-2 border-border align-top min-w-[280px]">
                      <div className="flex flex-col h-full relative">
                        <button 
                          onClick={() => removeFromCompare(p.id)}
                          className="absolute -top-2 -right-2 p-1.5 bg-background border border-border rounded-full text-muted-foreground hover:text-destructive hover:border-destructive transition-colors shadow-sm"
                          aria-label="Remove from comparison"
                        >
                          <XCircle className="h-4 w-4" />
                        </button>
                        
                        <div className="aspect-video w-full mb-4 bg-white rounded-lg border border-border flex items-center justify-center overflow-hidden p-4">
                          <img 
                            src={p.image_url || "https://placehold.co/600x400?text=No+Image"} 
                            alt={p.title}
                            className="max-w-full max-h-full object-contain"
                          />
                        </div>
                        
                        <h3 className="font-bold text-foreground text-base mb-2 line-clamp-2">{p.title}</h3>
                        
                        <div className="mt-auto pt-2">
                          {p.is_call_for_price || p.price_pkr === null ? (
                            <Badge variant="outline">Call for Price</Badge>
                          ) : (
                            <div className="font-bold text-lg text-[#1a73e8]">Rs {p.price_pkr.toLocaleString()}</div>
                          )}
                          
                          <div className="mt-2 text-xs flex items-center gap-1.5 font-medium">
                            {p.is_available ? (
                              <><CheckCircle2 className="h-3.5 w-3.5 text-green-500" /><span className="text-green-600">In Stock</span></>
                            ) : (
                              <><XCircle className="h-3.5 w-3.5 text-red-500" /><span className="text-red-600">Out of Stock</span></>
                            )}
                          </div>
                        </div>
                        
                        <Link 
                          to="/products/$productId"
                          params={{ productId: String(p.id) }}
                          className="mt-4 w-full block text-center py-2 bg-muted hover:bg-muted/80 text-foreground font-medium rounded-md transition-colors text-sm"
                        >
                          View Details
                        </Link>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {compareData.spec_keys.map(key => (
                  <tr key={key} className="hover:bg-muted/30 transition-colors">
                    <td className="p-4 border-b border-border font-medium text-sm text-foreground sticky left-0 bg-background/95 backdrop-blur z-10 shadow-[1px_0_0_0_#e2e8f0]">
                      {key}
                    </td>
                    {compareData.products.map(p => (
                      <td key={p.id} className="p-4 border-b border-border text-sm text-muted-foreground align-top">
                        {p.display_specs?.[key] || <span className="text-muted-foreground/30">—</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-20 text-center text-muted-foreground">
            Could not load product details.
          </div>
        )}
      </main>
    </div>
  );
}
