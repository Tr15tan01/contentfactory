"use client";

import { CheckCircle2, Loader2, X, XCircle } from "lucide-react";
import { formatBytes } from "@/lib/uploads";
import type { UploadItem } from "./use-uploader";

export function UploadTray({ items, onCancel, onClear }: { items: UploadItem[]; onCancel: (k: string) => void; onClear: () => void }) {
  if (!items.length) return null;
  const active = items.filter((i) => i.state === "uploading").length;
  return (
    <section
      aria-label="Uploads"
      className="fixed bottom-4 right-4 z-40 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-[var(--radius-card)] bg-surface shadow-[var(--shadow-frame)] ring-1 ring-line"
    >
      <header className="flex items-center justify-between border-b border-line px-4 py-2.5 text-sm">
        <span className="font-medium" role="status">{active ? `Uploading ${active} ${active === 1 ? "file" : "files"}` : "Uploads finished"}</span>
        {!active && <button onClick={onClear} className="text-muted hover:text-ink" aria-label="Close uploads"><X className="size-4" /></button>}
      </header>
      <ul className="max-h-64 divide-y divide-line overflow-y-auto">
        {items.map((i) => (
          <li key={i.key} className="grid gap-1.5 px-4 py-2.5 text-sm">
            <div className="flex items-center gap-2">
              {i.state === "uploading" ? <Loader2 className="size-4 shrink-0 animate-spin text-lab" aria-hidden /> : i.state === "done" ? <CheckCircle2 className="size-4 shrink-0 text-lab" aria-hidden /> : <XCircle className="size-4 shrink-0 text-signal" aria-hidden />}
              <span className="min-w-0 flex-1 truncate">{i.name}</span>
              <span className="text-xs text-muted">{formatBytes(i.size)}</span>
              {i.state === "uploading" && <button onClick={() => onCancel(i.key)} className="text-muted hover:text-ink" aria-label={`Cancel ${i.name}`}><X className="size-3.5" /></button>}
            </div>
            {i.state === "uploading" && (
              <div className="h-1 overflow-hidden rounded-full bg-sunk" role="progressbar" aria-valuenow={Math.round(i.progress * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={`Uploading ${i.name}`}>
                <div className="h-full bg-lab transition-[width]" style={{ width: `${Math.round(i.progress * 100)}%` }} />
              </div>
            )}
            {i.error && <p className="text-xs text-signal">{i.error}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
