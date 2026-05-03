import { useState } from "react";
import { Loader2, Sparkles, X } from "lucide-react";
import { api, type SearchResult } from "@/services/api";
import { Badge } from "@/components/ui/badge";
import { Link } from "@tanstack/react-router";

const FALLBACK_IMAGE = "https://images.unsplash.com/photo-1625842268584-8f3296236761?w=400&h=400&fit=crop";

interface Props {
  onClose: () => void;
}

export function AiSearchPanel({ onClose }: Props) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState("");
  const [topPicks, setTopPicks] = useState<SearchResult[]>([]);
  const [alternatives, setAlternatives] = useState<SearchResult[]>([]);
  const [error, setError] = useState("");

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError("");
    setExplanation("");
    setTopPicks([]);
    setAlternatives([]);

    try {
      const res = await api.search.recommend(query);
      setExplanation(res.explanation);
      setTopPicks(res.top_picks);
      setAlternatives(res.alternatives);
    } catch (err) {
      setError("AI search failed. Please try again or use the regular search bar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="pb-4 pt-1">
      <div className="w-full">
        {/* Header */}
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold text-foreground">AI-Assisted Search</span>
            <span className="text-xs text-muted-foreground">Describe what you need in plain language</span>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Input */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='e.g. "A budget gaming laptop under Rs. 80,000 with at least 16GB RAM"'
            className="flex-1 rounded-lg border border-input bg-background px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            autoFocus
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Search
          </button>
        </form>

        {/* Error */}
        {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

        {/* AI Explanation */}
        {explanation && (
          <div className="mt-4 rounded-lg border border-primary/20 bg-primary/5 p-4">
            <p className="text-sm leading-relaxed text-foreground">{explanation}</p>
          </div>
        )}

        {/* Top Picks */}
        {topPicks.length > 0 && (
          <div className="mt-4">
            <h3 className="mb-2 text-sm font-semibold text-foreground">
              ⭐ Top Picks ({topPicks.length})
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {topPicks.map((r) => (
                <ResultCard key={r.url} result={r} highlighted />
              ))}
            </div>
          </div>
        )}

        {/* Alternatives */}
        {alternatives.length > 0 && (
          <div className="mt-4">
            <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
              Other Matches ({alternatives.length})
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {alternatives.map((r) => (
                <ResultCard key={r.url} result={r} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ResultCard({ result, highlighted }: { result: SearchResult; highlighted?: boolean }) {
  return (
    <a
      href={result.url}
      target="_blank"
      rel="noopener noreferrer"
      className={`flex gap-3 rounded-lg border p-3 transition-shadow hover:shadow-sm ${
        highlighted ? "border-primary/40 bg-primary/5" : "border-border bg-card"
      }`}
    >
      <img
        src={result.image_url ?? FALLBACK_IMAGE}
        alt={result.title}
        className="h-16 w-16 flex-shrink-0 rounded-md object-cover"
        onError={(e) => { (e.target as HTMLImageElement).src = FALLBACK_IMAGE; }}
      />
      <div className="min-w-0 flex-1">
        <p className="line-clamp-2 text-xs font-semibold text-foreground">{result.title}</p>
        <p className="mt-1 text-xs font-bold text-primary">
          {result.price ? `Rs. ${result.price.toLocaleString()}` : "Call for Price"}
        </p>
        <div className="mt-1 flex items-center gap-1">
          <Badge variant="outline" className="text-xs px-1 py-0">
            {result.match_score}% match
          </Badge>
          {result.is_exact_match && (
            <Badge className="text-xs px-1 py-0">Exact</Badge>
          )}
        </div>
      </div>
    </a>
  );
}
