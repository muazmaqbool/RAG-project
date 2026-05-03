import { categoryTree } from "@/data/categories";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

interface Props {
  selectedCategory: string;
  selectedSubcategory: string;
  onSelect: (cat: string, sub: string) => void;
}

export function CategorySidebar({ selectedCategory, selectedSubcategory, onSelect }: Props) {
  return (
    <aside className="hidden lg:block w-60 shrink-0" role="navigation" aria-label="Product categories">
      <nav className="sticky top-20">
        <button
          onClick={() => onSelect("All", "")}
          className={`mb-1 w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-colors ${
            selectedCategory === "All"
              ? "bg-primary text-primary-foreground"
              : "text-foreground hover:bg-accent"
          }`}
        >
          All Products
        </button>

        <Accordion type="multiple" className="w-full">
          {categoryTree.map((cat) => (
            <AccordionItem key={cat.name} value={cat.name} className="border-b-0">
              <AccordionTrigger
                className={`px-3 py-2 text-sm font-medium hover:no-underline rounded-md transition-colors ${
                  selectedCategory === cat.name && !selectedSubcategory
                    ? "text-primary"
                    : "text-foreground"
                }`}
                onClick={() => onSelect(cat.name, "")}
              >
                {cat.name}
              </AccordionTrigger>
              <AccordionContent className="pb-1">
                <div className="ml-3 space-y-0.5 border-l border-border pl-3">
                  {cat.subcategories.map((subItem) => {
                    if (typeof subItem === "string") {
                      return (
                        <button
                          key={subItem}
                          onClick={() => onSelect(cat.name, subItem)}
                          className={`block w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                            selectedCategory === cat.name && selectedSubcategory === subItem
                              ? "bg-primary text-primary-foreground font-medium"
                              : "text-muted-foreground hover:text-foreground hover:bg-accent"
                          }`}
                        >
                          {subItem}
                        </button>
                      );
                    } else {
                      return (
                        <div key={subItem.name} className="py-1">
                          <button
                            onClick={() => onSelect(cat.name, subItem.name)}
                            className={`block w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                              selectedCategory === cat.name && selectedSubcategory === subItem.name
                                ? "bg-primary text-primary-foreground font-medium"
                                : "font-semibold text-foreground hover:bg-accent"
                            }`}
                          >
                            {subItem.name}
                          </button>
                          <div className="ml-2 mt-1 space-y-0.5 border-l border-border pl-2">
                            {subItem.subcategories.map((child) => {
                              const pathString = `${subItem.name} > ${child as string}`;
                              return (
                                <button
                                  key={child as string}
                                  onClick={() => onSelect(cat.name, pathString)}
                                  className={`block w-full rounded-md px-2 py-1 text-left text-xs transition-colors ${
                                    selectedCategory === cat.name && selectedSubcategory === pathString
                                      ? "bg-primary/20 text-primary font-medium"
                                      : "text-muted-foreground hover:text-primary hover:bg-accent"
                                  }`}
                                >
                                  {child as string}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      );
                    }
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </nav>
    </aside>
  );
}

export function CategoryPills({ selectedCategory, selectedSubcategory, onSelect }: Props) {
  return (
    <nav
      className="lg:hidden flex gap-2 overflow-x-auto px-4 py-3 scrollbar-hide border-b border-border"
      role="navigation"
      aria-label="Product categories"
    >
      <button
        onClick={() => onSelect("All", "")}
        className={`shrink-0 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
          selectedCategory === "All"
            ? "bg-primary text-primary-foreground"
            : "bg-secondary text-secondary-foreground hover:bg-accent"
        }`}
      >
        All
      </button>
      {categoryTree.map((cat) => (
        <button
          key={cat.name}
          onClick={() => onSelect(cat.name, "")}
          className={`shrink-0 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
            selectedCategory === cat.name
              ? "bg-primary text-primary-foreground"
              : "bg-secondary text-secondary-foreground hover:bg-accent"
          }`}
        >
          {cat.name}
        </button>
      ))}
    </nav>
  );
}
