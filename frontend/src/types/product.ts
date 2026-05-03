export interface Product {
  id: number;
  title: string;
  category: string;
  subcategory: string;
  price: number | null;
  originalPrice?: number;
  image: string;
  inStock: boolean;
  badge?: string;
  specs?: Record<string, string>;
  description?: string;
}

export interface CategoryTree {
  name: string;
  subcategories: (string | CategoryTree)[];
}
