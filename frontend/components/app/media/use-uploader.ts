"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";
import { uploadFile } from "@/lib/uploads";
import type { MediaAsset } from "@/types/api";

export interface UploadItem {
  key: string;
  name: string;
  size: number;
  progress: number;
  state: "uploading" | "done" | "error";
  error?: string;
  asset?: MediaAsset;
}

const CONCURRENCY = 3;

/** Upload queue with limited concurrency; the library refreshes as each file lands. */
export function useUploader(workspaceId: string, opts: { folderId?: string | null; onUploaded?: (a: MediaAsset) => void } = {}) {
  const queryClient = useQueryClient();
  const [items, setItems] = useState<UploadItem[]>([]);
  const controllers = useRef(new Map<string, AbortController>());
  const optsRef = useRef(opts);
  useEffect(() => {
    optsRef.current = opts;
  });

  const patch = (key: string, p: Partial<UploadItem>) => setItems((list) => list.map((i) => (i.key === key ? { ...i, ...p } : i)));

  const add = useCallback(
    async (files: FileList | File[]) => {
      const batch = Array.from(files).map((file) => ({ file, key: `${file.name}-${file.size}-${Math.random().toString(36).slice(2)}` }));
      setItems((list) => [...batch.map(({ file, key }) => ({ key, name: file.name, size: file.size, progress: 0, state: "uploading" as const })), ...list]);
      const queue = [...batch];
      const worker = async () => {
        for (let next = queue.shift(); next; next = queue.shift()) {
          const { file, key } = next;
          const controller = new AbortController();
          controllers.current.set(key, controller);
          try {
            const asset = await uploadFile(workspaceId, file, {
              folderId: optsRef.current.folderId,
              signal: controller.signal,
              onProgress: (p) => patch(key, { progress: p }),
            });
            patch(key, { state: "done", progress: 1, asset });
            optsRef.current.onUploaded?.(asset);
            void queryClient.invalidateQueries({ queryKey: ["media", workspaceId] });
          } catch (err) {
            const cancelled = (err as Error).name === "AbortError";
            patch(key, { state: "error", error: cancelled ? "Cancelled" : err instanceof ApiError ? err.message : "Upload failed." });
          } finally {
            controllers.current.delete(key);
          }
        }
      };
      await Promise.all(Array.from({ length: Math.min(CONCURRENCY, batch.length) }, worker));
      void queryClient.invalidateQueries({ queryKey: ["media-folders", workspaceId] });
      // Tidy the tray once everything landed; failures stay visible until dismissed.
      window.setTimeout(() => setItems((list) => (list.some((i) => i.state !== "done") ? list : [])), 4000);
    },
    [workspaceId, queryClient],
  );

  const cancel = (key: string) => controllers.current.get(key)?.abort();
  const clearFinished = () => setItems((list) => list.filter((i) => i.state === "uploading"));
  return { items, add, cancel, clearFinished, busy: items.some((i) => i.state === "uploading") };
}
