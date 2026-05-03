import { useState } from "react";
import { ChevronDown } from "lucide-react";

interface Props {
  specs: Record<string, string> | null | undefined;
  /** Optional ordered key list from master schema. Unordered keys appended at end. */
  schemaKeys?: string[];
}

export function SpecsTable({ specs, schemaKeys }: Props) {
  const [open, setOpen] = useState(false);

  if (!specs || Object.keys(specs).length === 0) return null;

  const filteredEntries = Object.entries(specs).filter(
    ([, v]) => v !== null && v !== undefined && String(v).trim() !== '',
  );

  if (filteredEntries.length === 0) return null;

  // Order by schema keys first if provided
  const ordered = schemaKeys
    ? [
        ...schemaKeys.filter((k) => specs[k] != null && String(specs[k]).trim()),
        ...filteredEntries.map(([k]) => k).filter((k) => !schemaKeys.includes(k)),
      ]
    : filteredEntries.map(([k]) => k);

  const count = ordered.length;

  return (
    <div className="specs-collapsible">
      <button
        className="specs-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        id="specs-toggle-btn"
      >
        <span className="specs-toggle-label">
          View Specifications
          <span className="specs-toggle-count">({count} items)</span>
        </span>
        <ChevronDown
          className={`specs-toggle-chevron ${open ? "specs-toggle-chevron--open" : ""}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div className="specs-table-wrap">
          <table className="specs-table">
            <tbody>
              {ordered.map((key) => {
                const value = specs[key];
                if (!value) return null;
                return (
                  <tr key={key} className="specs-row">
                    <td className="specs-key">{key}</td>
                    <td className="specs-val">{value}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
