import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";

interface MediaGalleryProps {
  onSelect: (url: string) => void;
  triggerLabel?: string;
  variant?: "outline" | "default" | "secondary" | "ghost" | "link";
  size?: "default" | "sm" | "lg" | "icon";
}

export function MediaGallery({ onSelect, triggerLabel = "Browse Gallery", variant = "outline", size = "sm" }: MediaGalleryProps) {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch the created /api/admin/media endpoint (which returns { media: [...] })
  const { data, isLoading } = useQuery({
    queryKey: ["admin-media"],
    queryFn: async () => {
      // Direct fetch utilizing VITE_API_URL and X-Admin-Key pattern
      const key = localStorage.getItem("adminKey") || "";
      const headers: Record<string, string> = { "X-Admin-Key": key };
      const res = await fetch(`${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api/admin/media`, { headers });
      if (!res.ok) throw new Error("Failed to load media");
      return res.json() as Promise<{ media: { id: number; filename: string; url: string; created_at: string }[] }>;
    },
    enabled: open, // Only fetch when gallery opens
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => await api.admin.uploadImage(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-media"] });
    },
  });

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadMutation.mutate(file);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={variant} size={size}>{triggerLabel}</Button>
      </DialogTrigger>
      {/* Remove focus trap on inner layer elements by not setting modal explicitly if we are inside another dialog, but it limits radix so we use e.stopPropagation */}
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto" onPointerDownOutside={(e) => e.preventDefault()} onInteractOutside={(e) => e.preventDefault()}>
        <DialogHeader className="flex flex-row justify-between items-center mb-4">
          <DialogTitle>Media Library</DialogTitle>
          <div className="flex gap-2">
             <input type="file" ref={fileInputRef} className="hidden" accept="image/*" onChange={handleUpload} />
             <Button size="sm" onClick={() => fileInputRef.current?.click()} disabled={uploadMutation.isPending}>
               {uploadMutation.isPending ? "Uploading..." : "Upload New Image"}
             </Button>
          </div>
        </DialogHeader>

        {isLoading ? (
          <div className="flex justify-center p-8"><span className="animate-pulse">Loading gallery...</span></div>
        ) : data?.media?.length === 0 ? (
          <div className="text-center p-8 text-muted-foreground border border-dashed rounded-md">
            No images uploaded yet.
          </div>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-4">
            {data?.media?.map((item) => (
              <div 
                key={item.id} 
                className="group relative aspect-square border border-border rounded-lg overflow-hidden bg-muted cursor-pointer hover:border-primary transition-all duration-200"
                onClick={() => {
                  onSelect(item.url);
                  setOpen(false);
                }}
              >
                <img src={item.url} alt={item.filename} className="w-full h-full object-cover" loading="lazy" />
                <div className="absolute inset-0 bg-background/0 group-hover:bg-background/20 transition-colors flex items-center justify-center">
                  <span className="opacity-0 group-hover:opacity-100 bg-primary text-primary-foreground text-xs px-2 py-1 rounded-md shadow-md transform scale-95 group-hover:scale-100 transition-all font-medium">
                    Select
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
