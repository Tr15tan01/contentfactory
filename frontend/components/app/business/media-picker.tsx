"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { mediaApi } from "@/lib/api/endpoints";
import type { MediaAsset } from "@/types/api";
import { cn } from "@/lib/utils";
import { MediaThumb } from "../media/media-tile";

/** Choose ready images from the library (product photos, logo). */
export function MediaPicker({
  workspaceId,
  open,
  onOpenChange,
  selected,
  onConfirm,
  max = 10,
  title = "Choose from your library",
  kind = "image",
}: {
  workspaceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selected: string[];
  onConfirm: (ids: string[], assets: MediaAsset[]) => void;
  max?: number;
  title?: string;
  kind?: "image" | "any";
}) {
  const [picked, setPicked] = useState(selected);
  const images = useQuery({
    queryKey: ["media", workspaceId, { picker: kind }],
    queryFn: () => mediaApi.list(workspaceId, { kind: kind === "image" ? "image" : undefined, limit: 100 }),
    enabled: open,
  });
  const ready = images.data?.items.filter((i) => i.status === "ready") ?? [];

  return (
    <Dialog open={open} onOpenChange={(o) => { if (o) setPicked(selected); onOpenChange(o); }}>
      <DialogContent title={title} description={max === 1 ? "Pick one." : `Pick up to ${max}.`} className="w-[min(46rem,calc(100vw-2rem))]">
        <div className="mt-5 max-h-[55vh] overflow-y-auto">
          {images.isPending ? (
            <p className="text-sm text-muted">Loading your library</p>
          ) : ready.length === 0 ? (
            <p className="text-sm text-muted">Nothing here yet. Upload photos and videos in Media first.</p>
          ) : (
            <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
              {ready.map((a) => {
                const on = picked.includes(a.id);
                return (
                  <li key={a.id}>
                    <button
                      type="button"
                      aria-pressed={on}
                      aria-label={a.display_name}
                      onClick={() => setPicked(max === 1 ? [a.id] : on ? picked.filter((x) => x !== a.id) : picked.length < max ? [...picked, a.id] : picked)}
                      className={cn("relative block w-full overflow-hidden rounded-[9px] ring-offset-2 ring-offset-surface", on && "ring-2 ring-lab")}
                    >
                      <MediaThumb asset={a} className="aspect-square" />
                      {on && <span className="absolute right-1.5 top-1.5 grid size-6 place-items-center rounded-full bg-lab text-on-lab"><Check className="size-3.5" /></span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={() => { onConfirm(picked, ready.filter((a) => picked.includes(a.id))); onOpenChange(false); }}>Use {picked.length || "no"} {picked.length === 1 ? "file" : "files"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
