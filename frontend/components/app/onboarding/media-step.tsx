"use client";

import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { mediaApi } from "@/lib/api/endpoints";
import { ACCEPT } from "@/lib/uploads";
import { cn } from "@/lib/utils";
import type { Business } from "@/types/api";
import { PreferencesForm } from "../business/preferences-form";
import { MediaThumb } from "../media/media-tile";
import { UploadTray } from "../media/upload-tray";
import { useUploader } from "../media/use-uploader";

export function MediaStep({ business, workspaceId, onSaved, secondary }: { business: Business; workspaceId: string; onSaved: () => void; secondary: React.ReactNode }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const uploader = useUploader(workspaceId);
  const recent = useQuery({
    queryKey: ["media", workspaceId, { recent: true }],
    queryFn: () => mediaApi.list(workspaceId, { limit: 12 }),
    refetchInterval: (q) => (q.state.data?.items.some((i) => i.status === "processing") ? 1500 : false),
  });

  return (
    <div className="grid gap-8">
      <div
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) void uploader.add(e.dataTransfer.files); }}
        className={cn("grid justify-items-center gap-3 rounded-[var(--radius-card)] border-2 border-dashed border-line-strong px-6 py-10 text-center transition-colors", over && "border-lab bg-lab-soft/50")}
      >
        <Upload className="size-6 text-lab" aria-hidden />
        <p className="font-medium">Drag photos and videos here</p>
        <p className="max-w-md text-sm text-muted">Your products, your space, your team at work. You can add tags and descriptions later in Media.</p>
        <input ref={input} type="file" multiple accept={ACCEPT} hidden onChange={(e) => { if (e.target.files?.length) void uploader.add(e.target.files); e.target.value = ""; }} />
        <Button type="button" variant="secondary" onClick={() => input.current?.click()}>Choose files</Button>
      </div>
      {!!recent.data?.items.length && (
        <div className="grid gap-2">
          <p className="text-sm text-muted">{recent.data.total} {recent.data.total === 1 ? "file" : "files"} in your library</p>
          <ul className="grid grid-cols-4 gap-2 sm:grid-cols-6">
            {recent.data.items.map((a) => <li key={a.id}><MediaThumb asset={a} className="aspect-square rounded-[9px]" /></li>)}
          </ul>
        </div>
      )}
      <PreferencesForm business={business} only="media" submitLabel="Continue" onSaved={onSaved} secondary={secondary} />
      <UploadTray items={uploader.items} onCancel={uploader.cancel} onClear={uploader.clearFinished} />
    </div>
  );
}
