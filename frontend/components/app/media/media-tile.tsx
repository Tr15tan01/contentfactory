"use client";

import { AlertTriangle, Copy, Film, Heart, Loader2 } from "lucide-react";
import { formatDuration } from "@/lib/uploads";
import { cn } from "@/lib/utils";
import type { MediaAsset } from "@/types/api";

export function MediaThumb({ asset, className }: { asset: MediaAsset; className?: string }) {
  const src = asset.thumbnail_url ?? (asset.kind === "image" ? asset.url : null);
  return (
    <div className={cn("relative overflow-hidden bg-sunk", className)}>
      {asset.status === "ready" && src ? (
        // eslint-disable-next-line @next/next/no-img-element -- signed storage URLs, already resized server-side
        <img src={src} alt={asset.description ?? asset.display_name} loading="lazy" decoding="async" className="size-full object-cover" />
      ) : asset.status === "processing" ? (
        <div className="grid size-full place-items-center text-muted">
          <span className="flex items-center gap-2 text-xs"><Loader2 className="size-4 animate-spin" aria-hidden /> Processing</span>
        </div>
      ) : asset.status === "failed" || asset.status === "quarantined" ? (
        <div className="grid size-full place-items-center p-3 text-center text-signal">
          <span className="grid justify-items-center gap-1 text-xs"><AlertTriangle className="size-4" aria-hidden /> Not added</span>
        </div>
      ) : (
        <div className="grid size-full place-items-center text-muted"><Film className="size-6" aria-hidden /></div>
      )}
      {asset.kind === "video" && asset.status === "ready" && (
        <span className="absolute bottom-1.5 left-1.5 inline-flex items-center gap-1 rounded bg-black/60 px-1.5 py-0.5 text-[0.6875rem] text-white">
          <Film className="size-3" aria-hidden />
          {asset.duration_seconds ? formatDuration(asset.duration_seconds) : "Video"}
        </span>
      )}
    </div>
  );
}

export function MediaTile({ asset, onOpen, selected }: { asset: MediaAsset; onOpen: () => void; selected?: boolean }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "group grid gap-2 rounded-[var(--radius-card)] p-1.5 text-left transition-colors hover:bg-sunk/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab",
        selected && "bg-lab-soft ring-2 ring-lab",
      )}
    >
      <div className="relative">
        <MediaThumb asset={asset} className="aspect-square rounded-[9px]" />
        {asset.is_favorite && (
          <Heart className="absolute right-2 top-2 size-4 fill-white text-white drop-shadow" aria-label="Favourite" />
        )}
        {(asset.source === "ai_generated" || asset.source === "assembled") && asset.status === "ready" && (
          <span className="absolute left-1.5 top-1.5 rounded bg-black/60 px-1.5 py-0.5 text-[0.6875rem] font-medium text-white">
            {asset.source === "assembled" ? "Built video" : asset.generator === "mock" ? "Placeholder" : "AI image"}
          </span>
        )}
        {asset.duplicate_of && (
          <span className="absolute right-1.5 top-1.5 inline-flex items-center gap-1 rounded bg-marker px-1.5 py-0.5 text-[0.6875rem] font-medium text-[#102326]">
            <Copy className="size-3" aria-hidden /> Duplicate
          </span>
        )}
      </div>
      <div className="grid gap-0.5 px-0.5">
        <span className="truncate text-sm font-medium">{asset.display_name}</span>
        <span className="truncate text-xs text-muted">{asset.tags.length ? asset.tags.join(", ") : "No tags yet"}</span>
      </div>
    </button>
  );
}
