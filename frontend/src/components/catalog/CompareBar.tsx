import { Link } from "@tanstack/react-router";
import { useCompare } from "@/hooks/use-compare";
import { X } from "lucide-react";

export function CompareBar() {
  const { ids, clearCompare, count } = useCompare();

  if (count < 2) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-card/95 shadow-lg backdrop-blur-sm">
      <div className="mx-auto flex max-w-screen-2xl items-center justify-between gap-4 px-4 py-3 lg:px-6">
        <p className="text-sm font-medium text-foreground">
          Comparing <span className="font-bold text-primary">{count}</span> product{count !== 1 ? "s" : ""}
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={clearCompare}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-3.5 w-3.5" />
            Clear all
          </button>
          <Link
            to="/compare"
            search={{ ids: ids.join(",") }}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            View Comparison →
          </Link>
        </div>
      </div>
    </div>
  );
}
