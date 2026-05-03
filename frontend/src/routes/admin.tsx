import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useRef, useMemo, useCallback, useEffect } from "react";
import "react-quill-new/dist/quill.snow.css";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, setAdminKey, clearAdminKey, type ProductSummary, type ProductDetail } from "@/services/api";
import { categoryTree } from "@/data/categories";
import { MediaGallery } from "@/components/admin/MediaGallery";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Search, Plus, Pencil, Trash2, ArrowLeft, X, Sparkles, Loader2, LogOut, Eye, Star } from "lucide-react";

export const Route = createFileRoute("/admin")({
  component: AdminRoot,
  head: () => ({
    meta: [
      { title: "Admin — Al-Aqsa Computers CMS" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
});

// ---------------------------------------------------------------------------
// Auth gate
// ---------------------------------------------------------------------------
function AdminRoot() {
  const [authed, setAuthed] = useState(() => !!sessionStorage.getItem("admin_key"));
  const [keyInput, setKeyInput] = useState("");
  const [authError, setAuthError] = useState("");

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setAdminKey(keyInput);
    // Test the key against a real admin-guarded endpoint
    try {
      await api.admin.history(0);
      setAuthed(true);
      setAuthError("");
    } catch (err: any) {
      if (err.message && err.message.toLowerCase().includes("invalid")) {
        clearAdminKey();
        setAuthError("Invalid admin key. Please try again.");
      } else {
        // Any other error like 404 (Product not found) means we passed the auth gate!
        setAuthed(true);
        setAuthError("");
      }
    }
  }

  if (!authed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm rounded-xl border border-border bg-card p-8 shadow-sm">
          <h1 className="mb-1 text-xl font-bold text-foreground">Admin Access</h1>
          <p className="mb-6 text-sm text-muted-foreground">Enter your admin key to continue.</p>
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <Label htmlFor="admin-key">Admin Key</Label>
              <Input
                id="admin-key"
                type="password"
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder="Enter secret key..."
                className="mt-1"
                autoFocus
              />
            </div>
            {authError && <p className="text-sm text-destructive">{authError}</p>}
            <Button type="submit" className="w-full">Sign In</Button>
          </form>
        </div>
      </div>
    );
  }

  return <AdminDashboard onLogout={() => { clearAdminKey(); setAuthed(false); }} />;
}

// ---------------------------------------------------------------------------
// Form state
// ---------------------------------------------------------------------------
interface SpecRow { key: string; value: string; }

const emptyForm = {
  title: "",
  category: "",
  subcategory: "",
  price_pkr: "",
  image_url: "",
  image_urls: "",
  is_available: true,
  is_call_for_price: false,
  short_description: "",
  long_description: "",
};

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------
function AdminDashboard({ onLogout }: { onLogout: () => void }) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [specs, setSpecs] = useState<SpecRow[]>([]);
  const [enrichingId, setEnrichingId] = useState<number | null>(null);
  const [enrichMessage, setEnrichMessage] = useState("");

  const limit = 20;

  const quillRef = useRef<any>(null);

  // SSR-safe dynamic import for ReactQuill
  const [QuillEditor, setQuillEditor] = useState<any>(null);
  useEffect(() => {
    import("react-quill-new").then((module) => {
      setQuillEditor(() => module.default);
    });
  }, []);

  const imageHandler = useCallback(() => {
    const input = document.createElement("input");
    input.setAttribute("type", "file");
    input.setAttribute("accept", "image/*");
    input.click();

    input.onchange = async () => {
      const file = input.files ? input.files[0] : null;
      if (!file) return;

      try {
        const { url } = await api.admin.uploadImage(file);
        const quill = quillRef.current?.getEditor();
        const range = quill?.getSelection();
        if (quill) {
          quill.insertEmbed(range?.index ?? 0, "image", url);
        }
      } catch (err) {
        alert("Image upload failed");
      }
    };
  }, []);

  const modules = useMemo(
    () => ({
      toolbar: {
        container: [
          [{ header: [1, 2, 3, false] }],
          ["bold", "italic", "underline", "strike", "blockquote"],
          [{ list: "ordered" }, { list: "bullet" }],
          [{ align: [] }, { color: [] }, { background: [] }],
          ["link", "image"],
          ["clean"],
        ],
        handlers: {
          image: imageHandler,
        },
      },
      // Ensure tables are enabled properly on quill (built-in snow feature if validly registered, though we might need quill-table module conventionally, natively lists/headers are supported)
    }),
    [imageHandler]
  );

  const { data, isLoading } = useQuery({
    queryKey: ["admin-products", page, search],
    queryFn: () => api.products.list({ page, limit, search: search || undefined, available_only: false }),
  });

  const products = data?.results ?? [];
  const totalPages = data?.pages ?? 1;
  const selectedCat = categoryTree.find((c) => c.name === form.category);

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.admin.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-products"] }),
  });

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<ProductDetail>) =>
      editingId !== null ? api.admin.update(editingId, payload) : api.admin.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-products"] });
      setDialogOpen(false);
    },
  });

  const toggleFeaturedMutation = useMutation({
    mutationFn: (id: number) => api.admin.toggleFeatured(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-products"] }),
  });

  function openCreate() {
    setEditingId(null);
    setForm(emptyForm);
    setSpecs([]);
    setDialogOpen(true);
  }

  function openEdit(p: ProductSummary) {
    setEditingId(p.id);
    setForm({
      title: p.title,
      category: p.leaf_category?.split(">")[0]?.trim() ?? "",
      subcategory: p.leaf_category?.split(">")[1]?.trim() ?? "",
      price_pkr: p.price_pkr != null ? String(p.price_pkr) : "",
      image_url: p.image_url ?? "",
      image_urls: (p.image_urls || []).join(", "),
      is_available: p.is_available,
      is_call_for_price: p.is_call_for_price,
      short_description: p.short_description ?? "",
      long_description: "",
    });
    setSpecs([]);
    setDialogOpen(true);
  }

  async function handleEnrich(id: number) {
    setEnrichingId(id);
    setEnrichMessage("");
    try {
      const res = await api.admin.enrich(id);
      setEnrichMessage(`✓ "${res.title}" enriched — ${res.search_specs_keys?.length ?? 0} spec keys extracted.`);
      qc.invalidateQueries({ queryKey: ["admin-products"] });
    } catch (e: unknown) {
      setEnrichMessage(`❌ Enrichment failed: ${(e as Error).message}`);
    } finally {
      setEnrichingId(null);
    }
  }

  function handleSave() {
    const specsObj = specs.reduce(
      (acc, s) => (s.key ? { ...acc, [s.key]: s.value } : acc),
      {} as Record<string, string>,
    );

    const payload: Partial<ProductDetail> = {
      title: form.title,
      leaf_category: form.category && form.subcategory
        ? `${form.category} > ${form.subcategory}`
        : form.category,
      price_pkr: form.price_pkr ? Number(form.price_pkr) : null,
      is_call_for_price: form.is_call_for_price,
      is_available: form.is_available,
      image_url: form.image_url || null,
      image_urls: form.image_urls ? form.image_urls.split(",").map((s) => s.trim()).filter(Boolean) : [],
      short_description: form.short_description || null,
      long_description: form.long_description || null,
      display_specs: Object.keys(specsObj).length > 0 ? specsObj : undefined,
    };

    saveMutation.mutate(payload);
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card px-4 py-4 lg:px-6">
        <div className="mx-auto flex max-w-screen-xl items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="text-muted-foreground hover:text-foreground transition-colors">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <h1 className="text-xl font-bold text-foreground">Admin CMS</h1>
            {data && (
              <span className="text-sm text-muted-foreground">
                {data.total.toLocaleString()} total products
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={openCreate} size="sm">
              <Plus className="h-4 w-4" />
              Add Product
            </Button>
            <Button variant="ghost" size="icon" onClick={onLogout} title="Log out">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-screen-xl px-4 py-6 lg:px-6">
        {/* Enrich message */}
        {enrichMessage && (
          <div className={`mb-4 rounded-lg border px-4 py-3 text-sm ${enrichMessage.startsWith("✓") ? "border-green-200 bg-green-50 text-green-700" : "border-destructive/30 bg-destructive/5 text-destructive"}`}>
            {enrichMessage}
          </div>
        )}

        {/* Search */}
        <div className="relative mb-4 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search products..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            className="pl-10"
          />
        </div>

        {/* Table */}
        <div className="rounded-lg border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">ID</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                    Loading...
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && products.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-mono text-xs">{p.id}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <img
                        src={p.image_url || "https://images.unsplash.com/photo-1625842268584-8f3296236761?w=400&h=400&fit=crop"}
                        alt={p.title}
                        className="h-10 w-10 rounded-md object-cover flex-shrink-0 border border-border"
                        onError={(e) => { (e.target as HTMLImageElement).src = "https://images.unsplash.com/photo-1625842268584-8f3296236761?w=400&h=400&fit=crop"; }}
                      />
                      <span className="max-w-[220px] truncate font-medium">{p.title}</span>
                    </div>
                  </TableCell>
                  <TableCell className="max-w-[160px] truncate text-xs text-muted-foreground">{p.leaf_category}</TableCell>
                  <TableCell>
                    {p.is_call_for_price || p.price_pkr == null ? (
                      <Badge variant="outline" className="text-xs">Call</Badge>
                    ) : (
                      <span className="font-semibold text-sm">Rs. {p.price_pkr.toLocaleString()}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={p.is_available ? "default" : "destructive"} className="text-xs">
                      {p.is_available ? "Available" : "Hidden"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" asChild title="View on site">
                        <Link to="/products/$productId" params={{ productId: String(p.id) }} target="_blank">
                          <Eye className="h-4 w-4" />
                        </Link>
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        onClick={() => toggleFeaturedMutation.mutate(p.id)} 
                        title={p.is_featured ? "Remove from Featured" : "Mark as Featured"}
                      >
                        <Star className={`h-4 w-4 ${p.is_featured ? 'fill-yellow-400 text-yellow-400' : ''}`} />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => openEdit(p)} title="Edit">
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleEnrich(p.id)}
                        disabled={enrichingId === p.id}
                        title="AI Enrich"
                      >
                        {enrichingId === p.id
                          ? <Loader2 className="h-4 w-4 animate-spin" />
                          : <Sparkles className="h-4 w-4 text-primary" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => { if (confirm(`Delete "${p.title}"?`)) deleteMutation.mutate(p.id); }}
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!isLoading && products.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                    No products found.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-center gap-2">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page + 1} of {totalPages}
            </span>
            <Button variant="outline" size="sm" disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        )}
      </div>

      {/* Create / Edit Dialog - modal={false} used to NOT trap focus natively which breaks react-quill */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen} modal={false}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" onPointerDownOutside={(e) => e.preventDefault()} onInteractOutside={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle>{editingId !== null ? "Edit Product" : "Add Product"}</DialogTitle>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            {/* Title */}
            <div>
              <Label>Title</Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>

            {/* Category / Subcategory */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Category</Label>
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v, subcategory: "" })}>
                  <SelectTrigger><SelectValue placeholder="Select..." /></SelectTrigger>
                  <SelectContent>
                    {categoryTree.map((c) => (
                      <SelectItem key={c.name} value={c.name}>{c.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Subcategory</Label>
                <Select value={form.subcategory} onValueChange={(v) => setForm({ ...form, subcategory: v })}>
                  <SelectTrigger><SelectValue placeholder="Select..." /></SelectTrigger>
                  <SelectContent>
                    {selectedCat
                      ? (() => {
                          const flatten = (subs: any[], prefix = ""): string[] => {
                            let res: string[] = [];
                            for (const s of subs) {
                              if (typeof s === "string") res.push(prefix ? `${prefix} > ${s}` : s);
                              else {
                                res.push(prefix ? `${prefix} > ${s.name}` : s.name);
                                res.push(...flatten(s.subcategories, prefix ? `${prefix} > ${s.name}` : s.name));
                              }
                            }
                            return res;
                          };
                          return flatten(selectedCat.subcategories).map((s) => (
                            <SelectItem key={s} value={s}>
                              {s}
                            </SelectItem>
                          ));
                        })()
                      : null}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Price */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Price (PKR)</Label>
                <Input type="number" value={form.price_pkr} onChange={(e) => setForm({ ...form, price_pkr: e.target.value })} placeholder="Leave empty for 'Call for Price'" />
              </div>
              <div className="flex flex-col justify-end gap-2">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={form.is_call_for_price} onChange={(e) => setForm({ ...form, is_call_for_price: e.target.checked })} />
                  Call for Price
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={form.is_available} onChange={(e) => setForm({ ...form, is_available: e.target.checked })} />
                  Available / Visible
                </label>
              </div>
            </div>

            {/* Image URLs */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div className="flex justify-between items-center mb-1">
                  <Label>Main Image URL</Label>
                  <MediaGallery onSelect={(url) => setForm({ ...form, image_url: url })} />
                </div>
                <Input value={form.image_url} onChange={(e) => setForm({ ...form, image_url: e.target.value })} />
              </div>
              <div>
                <div className="flex justify-between items-center mb-1">
                  <Label>Additional Images (comma separated)</Label>
                  <MediaGallery onSelect={(url) => setForm({ ...form, image_urls: form.image_urls ? `${form.image_urls}, ${url}` : url })} />
                </div>
                <Input value={form.image_urls} onChange={(e) => setForm({ ...form, image_urls: e.target.value })} placeholder="https://..., https://..." />
              </div>
            </div>

            {/* Short Description */}
            <div>
              <Label>Short Description (one bullet per line)</Label>
              <Textarea
                value={form.short_description}
                onChange={(e) => setForm({ ...form, short_description: e.target.value })}
                rows={4}
                placeholder="Fast SSD storage&#10;Full HD IPS display&#10;Long battery life"
              />
            </div>

            {/* Long Description */}
            <div>
              <Label>Long Description (HTML supported)</Label>
              <div className="mt-1">
                {QuillEditor ? (
                  <QuillEditor
                    ref={quillRef}
                    theme="snow"
                    value={form.long_description}
                    onChange={(val: string) => setForm({ ...form, long_description: val })}
                    modules={modules}
                    className="bg-background rounded-md [&_.ql-editor]:min-h-[200px]"
                  />
                ) : (
                  <div className="min-h-[200px] border border-border rounded-md bg-muted animate-pulse" />
                )}
              </div>
            </div>

            {/* Specifications builder */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <Label>Specifications</Label>
                <Button type="button" variant="outline" size="sm" onClick={() => setSpecs([...specs, { key: "", value: "" }])}>
                  <Plus className="h-3 w-3 mr-1" />Add Row
                </Button>
              </div>
              {specs.length > 0 && (
                <div className="space-y-2">
                  {specs.map((s, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <Input
                        placeholder="Key (e.g. RAM)"
                        value={s.key}
                        onChange={(e) => { const n = [...specs]; n[i] = { ...n[i], key: e.target.value }; setSpecs(n); }}
                        className="flex-1"
                      />
                      <Input
                        placeholder="Value (e.g. 16GB)"
                        value={s.value}
                        onChange={(e) => { const n = [...specs]; n[i] = { ...n[i], value: e.target.value }; setSpecs(n); }}
                        className="flex-1"
                      />
                      <Button type="button" variant="ghost" size="icon" onClick={() => setSpecs(specs.filter((_, j) => j !== i))}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <Button
              onClick={handleSave}
              disabled={saveMutation.isPending}
              className="mt-2 w-full"
            >
              {saveMutation.isPending
                ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving...</>
                : editingId !== null ? "Update Product" : "Create Product"}
            </Button>

            {saveMutation.isError && (
              <p className="text-sm text-destructive">{(saveMutation.error as Error).message}</p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
