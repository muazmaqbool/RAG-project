import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { ChevronDown, X } from "lucide-react";

export interface FilterState {
  minPrice: number | undefined;
  maxPrice: number | undefined;
  brand: string;
  processor: string;
  ram: string;
}

interface Props {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
  id,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
  id: string;
}) {
  return (
    <div className="filter-group">
      <label htmlFor={id} className="filter-group-label">
        {label}
      </label>
      <div className="filter-select-wrap">
        <select
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="filter-select"
        >
          <option value="">All</option>
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        <ChevronDown className="filter-select-icon" aria-hidden="true" />
      </div>
    </div>
  );
}

export function FilterPanel({ filters, onChange }: Props) {
  const { data: options } = useQuery({
    queryKey: ["filter-options"],
    queryFn: () => api.products.filterOptions(),
    staleTime: 1000 * 60 * 10, // 10 min
  });

  // Local price inputs (controlled separately so user can type freely)
  const [localMin, setLocalMin] = useState<string>(
    filters.minPrice !== undefined ? String(filters.minPrice) : ""
  );
  const [localMax, setLocalMax] = useState<string>(
    filters.maxPrice !== undefined ? String(filters.maxPrice) : ""
  );

  // Sync local to parent after user stops typing (300 ms debounce)
  useEffect(() => {
    const timer = setTimeout(() => {
      const min = localMin ? parseInt(localMin, 10) : undefined;
      const max = localMax ? parseInt(localMax, 10) : undefined;
      if (min !== filters.minPrice || max !== filters.maxPrice) {
        onChange({ ...filters, minPrice: min, maxPrice: max });
      }
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localMin, localMax]);

  const hasActiveFilters =
    filters.minPrice !== undefined ||
    filters.maxPrice !== undefined ||
    filters.brand ||
    filters.processor ||
    filters.ram;

  function clearAll() {
    setLocalMin("");
    setLocalMax("");
    onChange({ minPrice: undefined, maxPrice: undefined, brand: "", processor: "", ram: "" });
  }

  return (
    <aside className="filter-panel" aria-label="Product filters">
      <div className="filter-panel-header">
        <h2 className="filter-panel-title">Filter Products</h2>
        {hasActiveFilters && (
          <button
            id="clear-all-filters"
            onClick={clearAll}
            className="filter-clear-btn"
            aria-label="Clear all filters"
          >
            <X className="h-3 w-3" />
            Clear All
          </button>
        )}
      </div>

      {/* Price range */}
      <div className="filter-group">
        <span className="filter-group-label">Price Range (Rs.)</span>
        <div className="filter-price-row">
          <input
            id="filter-min-price"
            type="number"
            placeholder={options ? `Min ${options.min_price.toLocaleString()}` : "Min"}
            value={localMin}
            onChange={(e) => setLocalMin(e.target.value)}
            className="filter-price-input"
            min={0}
            aria-label="Minimum price"
          />
          <span className="filter-price-sep">–</span>
          <input
            id="filter-max-price"
            type="number"
            placeholder={options ? `Max ${options.max_price.toLocaleString()}` : "Max"}
            value={localMax}
            onChange={(e) => setLocalMax(e.target.value)}
            className="filter-price-input"
            min={0}
            aria-label="Maximum price"
          />
        </div>
      </div>

      <FilterSelect
        id="filter-brand"
        label="Brand"
        value={filters.brand}
        options={options?.brands ?? []}
        onChange={(v) => onChange({ ...filters, brand: v })}
      />

      <FilterSelect
        id="filter-processor"
        label="Processor"
        value={filters.processor}
        options={options?.processors ?? []}
        onChange={(v) => onChange({ ...filters, processor: v })}
      />

      <FilterSelect
        id="filter-ram"
        label="RAM"
        value={filters.ram}
        options={options?.rams ?? []}
        onChange={(v) => onChange({ ...filters, ram: v })}
      />
    </aside>
  );
}
