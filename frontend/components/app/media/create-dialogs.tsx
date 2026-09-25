"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, FlaskConical, Plus, Trash2 } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { contentApi, mediaApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";
import type { MediaAsset } from "@/types/api";
import { MediaPicker } from "../business/media-picker";
import { MediaThumb } from "./media-tile";

const errText = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Try again.");

function useInvalidate(ws: string, contentId?: string | null) {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["media", ws] });
    void qc.invalidateQueries({ queryKey: ["usage", ws] });
    if (contentId) void qc.invalidateQueries({ queryKey: ["content-item", ws, contentId] });
  };
}

export function GenerateImageDialog({ ws, open, onOpenChange, contentId, initialPrompt = "", onCreated }: {
  ws: string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  contentId?: string | null;
  initialPrompt?: string;
  onCreated?: (asset: MediaAsset, reused: boolean) => void;
}) {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [aspect, setAspect] = useState("square");
  const [useBrand, setUseBrand] = useState(true);
  const usage = useQuery({ queryKey: ["usage", ws], queryFn: () => contentApi.usage(ws), enabled: open });
  const invalidate = useInvalidate(ws, contentId);
  const create = useMutation({
    mutationFn: () => mediaApi.generateImage(ws, { prompt, aspect, use_brand: useBrand, content_id: contentId ?? null }),
    onSuccess: ({ asset, reused }) => { invalidate(); onCreated?.(asset, reused); onOpenChange(false); },
  });
  const left = usage.data?.images.remaining;
  return (
    <Dialog open={open} onOpenChange={(o) => { if (o) { setPrompt(initialPrompt); create.reset(); } onOpenChange(o); }}>
      <DialogContent title="Generate an image" description={contentId ? "It's added to this post and saved in your media library." : "It's saved in your media library."} className="w-[min(36rem,calc(100vw-2rem))]">
        <form className="mt-5 grid gap-4" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          {create.error && <Alert tone="error" title="Not generated">{errText(create.error)}</Alert>}
          {usage.data?.image_provider === "mock" && (
            <p className="flex gap-2 rounded-md bg-marker-soft px-3 py-2 text-xs text-ink dark:text-marker"><FlaskConical className="mt-0.5 size-3.5 shrink-0" aria-hidden />Development mode: this server draws a labelled placeholder instead of calling an image model.</p>
          )}
          <Field id="img-prompt" label="Describe the image">
            <Textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} className="min-h-24" required minLength={3} maxLength={1000} placeholder="A cardamom bun on a wooden counter, morning light" />
          </Field>
          <div className="flex flex-wrap items-end gap-4">
            <Field id="img-aspect" label="Shape" className="w-48">
              <Select value={aspect} onChange={(e) => setAspect(e.target.value)}>
                <option value="square">Square (feed)</option>
                <option value="portrait">Portrait (feed)</option>
                <option value="landscape">Landscape</option>
                <option value="story">Tall (story)</option>
              </Select>
            </Field>
            <label className="flex h-11 items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--lab)]" checked={useBrand} onChange={(e) => setUseBrand(e.target.checked)} /> Use my brand colours and style</label>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <p className="text-sm text-muted">{left === undefined ? "" : `${left} image${left === 1 ? "" : "s"} left this period. The same request again is free.`}</p>
            <Button type="submit" loading={create.isPending} disabled={left === 0}>Generate</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface Scene {
  asset: MediaAsset | null;
  duration: number;
  text: string;
}

export function BuildVideoDialog({ ws, open, onOpenChange, contentId, initialScenes, title, onCreated }: {
  ws: string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  contentId?: string | null;
  initialScenes?: { text: string; duration: number }[];
  title?: string;
  onCreated?: (asset: MediaAsset, reused: boolean) => void;
}) {
  const start = () => (initialScenes?.length ? initialScenes.map((s) => ({ asset: null, duration: Math.min(30, Math.max(1, s.duration)), text: s.text })) : [{ asset: null, duration: 3, text: "" }]);
  const [scenes, setScenes] = useState<Scene[]>(start);
  const [aspect, setAspect] = useState("vertical");
  const [picking, setPicking] = useState<number | null>(null);
  const usage = useQuery({ queryKey: ["usage", ws], queryFn: () => contentApi.usage(ws), enabled: open });
  const invalidate = useInvalidate(ws, contentId);
  const total = scenes.reduce((s, x) => s + x.duration, 0);
  const credits = Math.max(1, Math.ceil(total / 30));
  const ready = scenes.every((s) => s.asset) && total <= 90;
  const build = useMutation({
    mutationFn: () => mediaApi.buildVideo(ws, { scenes: scenes.map((s) => ({ media_id: s.asset!.id, duration_s: s.duration, text: s.text || undefined })), aspect, title, content_id: contentId ?? null }),
    onSuccess: ({ asset, reused }) => { invalidate(); onCreated?.(asset, reused); onOpenChange(false); },
  });
  const set = (i: number, patch: Partial<Scene>) => setScenes((all) => all.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const move = (i: number, d: -1 | 1) => setScenes((all) => { const next = [...all]; [next[i], next[i + d]] = [next[i + d]!, next[i]!]; return next; });
  const left = usage.data?.video_credits.remaining;

  return (
    <Dialog open={open} onOpenChange={(o) => { if (o) { setScenes(start()); build.reset(); } onOpenChange(o); }}>
      <DialogContent title="Build a video" description="From your own photos and clips, in order, with optional on-screen text. Photos are shown for the time you set; clips play from the start." className="w-[min(46rem,calc(100vw-2rem))] max-h-[92vh] overflow-y-auto">
        <div className="mt-5 grid gap-4">
          {build.error && <Alert tone="error" title="Not built">{errText(build.error)}</Alert>}
          {usage.data && !usage.data.video_builder && <Alert tone="info" title="Not available on this server">Video building needs ffmpeg on the server.</Alert>}
          <ol className="grid gap-3">
            {scenes.map((s, i) => (
              <li key={i} className="grid grid-cols-[4.5rem_1fr_auto] items-start gap-3 rounded-[var(--radius-control)] p-2 ring-1 ring-line">
                <button type="button" onClick={() => setPicking(i)} className={cn("overflow-hidden rounded-md", !s.asset && "grid size-[4.5rem] place-items-center bg-sunk text-xs text-muted")} aria-label={`Choose media for scene ${i + 1}`}>
                  {s.asset ? <MediaThumb asset={s.asset} className="size-[4.5rem]" /> : <><Plus className="size-4" aria-hidden />Choose</>}
                </button>
                <div className="grid gap-2">
                  <Input value={s.text} onChange={(e) => set(i, { text: e.target.value })} maxLength={120} placeholder={`On-screen text for scene ${i + 1} (optional)`} className="h-9" aria-label={`Scene ${i + 1} text`} />
                  <label className="flex items-center gap-2 text-sm text-muted">
                    Seconds <Input type="number" min={1} max={30} step={0.5} value={s.duration} onChange={(e) => set(i, { duration: Math.min(30, Math.max(1, Number(e.target.value) || 1)) })} className="h-9 w-20" aria-label={`Scene ${i + 1} seconds`} />
                  </label>
                </div>
                <div className="flex flex-col gap-1">
                  <Button type="button" size="icon" variant="ghost" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Move up"><ArrowUp className="size-4" /></Button>
                  <Button type="button" size="icon" variant="ghost" disabled={i === scenes.length - 1} onClick={() => move(i, 1)} aria-label="Move down"><ArrowDown className="size-4" /></Button>
                  <Button type="button" size="icon" variant="ghost" disabled={scenes.length === 1} onClick={() => setScenes(scenes.filter((_, j) => j !== i))} aria-label="Remove scene"><Trash2 className="size-4" /></Button>
                </div>
              </li>
            ))}
          </ol>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" variant="secondary" size="sm" disabled={scenes.length >= 20} onClick={() => setScenes([...scenes, { asset: null, duration: 3, text: "" }])}><Plus /> Add scene</Button>
            <Select value={aspect} onChange={(e) => setAspect(e.target.value)} className="h-9 w-48 text-sm" aria-label="Shape">
              <option value="vertical">Vertical 9:16 (Reels, Shorts)</option>
              <option value="square">Square 1:1</option>
            </Select>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <p className={cn("numeric text-sm", total > 90 ? "text-signal" : "text-muted")}>
              {total.toFixed(1)} s, {credits} video credit{credits === 1 ? "" : "s"}{left !== undefined ? ` (${left} left)` : ""}{total > 90 ? ". Keep it under 90 seconds." : ""}
            </p>
            <Button onClick={() => build.mutate()} loading={build.isPending} disabled={!ready || (left !== undefined && left < credits) || usage.data?.video_builder === false}>Build video</Button>
          </div>
        </div>
        <MediaPicker workspaceId={ws} open={picking !== null} onOpenChange={(o) => !o && setPicking(null)} kind="any" max={1} title="Choose a photo or clip"
          selected={picking !== null && scenes[picking]?.asset ? [scenes[picking]!.asset!.id] : []}
          onConfirm={(_, assets) => { if (picking !== null && assets[0]) set(picking, { asset: assets[0] }); setPicking(null); }} />
      </DialogContent>
    </Dialog>
  );
}
