"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Heart, Trash2 } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ChipsInput } from "@/components/ui/chips-input";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { mediaApi } from "@/lib/api/endpoints";
import { formatBytes, formatDuration } from "@/lib/uploads";
import { cn } from "@/lib/utils";
import type { MediaAsset, MediaFolder } from "@/types/api";

const normalizeTag = (v: string) => v.trim().replace(/^#/, "").toLowerCase().replace(/\s+/g, " ").slice(0, 64);

function Editor({ workspaceId, asset, folders, tagSuggestions, canEdit, onClose }: {
  workspaceId: string;
  asset: MediaAsset;
  folders: MediaFolder[];
  tagSuggestions: string[];
  canEdit: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(asset.display_name);
  const [description, setDescription] = useState(asset.description ?? "");
  const [tags, setTags] = useState(asset.tags);
  const [folder, setFolder] = useState(asset.folder_id ?? "");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["media", workspaceId] });
    void queryClient.invalidateQueries({ queryKey: ["media-folders", workspaceId] });
    void queryClient.invalidateQueries({ queryKey: ["media-tags", workspaceId] });
  };

  const save = useMutation({
    mutationFn: () =>
      mediaApi.update(workspaceId, asset.id, {
        display_name: name.trim() || asset.display_name,
        description,
        tags,
        ...(folder ? { folder_id: folder } : { move_to_unfiled: true }),
      }),
    onSuccess: () => {
      refresh();
      onClose();
    },
  });
  const favorite = useMutation({
    mutationFn: () => mediaApi.update(workspaceId, asset.id, { is_favorite: !asset.is_favorite }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => mediaApi.remove(workspaceId, asset.id),
    onSuccess: () => {
      refresh();
      onClose();
    },
  });

  const facts = [
    asset.width && asset.height ? `${asset.width} × ${asset.height}` : null,
    asset.duration_seconds ? formatDuration(asset.duration_seconds) : null,
    formatBytes(asset.size_bytes),
    new Date(asset.created_at).toLocaleDateString("en-US", { dateStyle: "medium" }),
  ].filter(Boolean);

  return (
    <div className="mt-5 grid gap-6 md:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <div className="grid content-start gap-3">
        <div className="grid max-h-[60vh] place-items-center overflow-hidden rounded-[var(--radius-card)] bg-sunk">
          {asset.status === "ready" && asset.url ? (
            asset.kind === "video" ? (
              <video src={asset.url} poster={asset.thumbnail_url ?? undefined} controls preload="metadata" className="max-h-[60vh] w-full" />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element -- signed storage URL
              <img src={asset.url} alt={asset.description ?? asset.display_name} className="max-h-[60vh] w-full object-contain" />
            )
          ) : (
            <p className="p-10 text-sm text-muted">{asset.error ?? "This file is still being processed."}</p>
          )}
        </div>
        <p className="text-sm text-muted">{facts.join(", ")}</p>
        {asset.source === "ai_generated" && (
          <p className="text-xs text-muted">
            {asset.generator === "mock" ? "Development placeholder, not made by an AI model." : "AI-generated image."} The prompt is saved as its description.
          </p>
        )}
        {asset.source === "assembled" && <p className="text-xs text-muted">Video built from your own photos and clips.</p>}
        {asset.duplicate_of && (
          <Alert tone="info" title="You already have this file">
            The same photo or video is in your library. You can delete this copy.
          </Alert>
        )}
      </div>

      <form
        className="grid content-start gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        {save.error && <Alert tone="error" title="Changes not saved">{save.error instanceof ApiError ? save.error.message : "Try again."}</Alert>}
        <Field id="media-name" label="Name">
          <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={255} disabled={!canEdit} />
        </Field>
        <Field id="media-description" label="Description" hint="What's in it? Your agent reads this when choosing media for a post.">
          <Textarea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} rows={3} className="min-h-24" disabled={!canEdit} />
        </Field>
        <Field id="media-tags" label="Tags" hint="Products, themes, seasons. Press Enter after each.">
          <ChipsInput value={tags} onChange={setTags} suggestions={tagSuggestions} max={30} normalize={normalizeTag} placeholder="latte, summer, team" />
        </Field>
        <Field id="media-folder" label="Folder">
          <Select value={folder} onChange={(e) => setFolder(e.target.value)} disabled={!canEdit}>
            <option value="">Unfiled</option>
            {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </Select>
        </Field>
        {canEdit && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button type="submit" loading={save.isPending}>Save</Button>
            <Button type="button" variant="secondary" onClick={() => favorite.mutate()} loading={favorite.isPending} aria-pressed={asset.is_favorite}>
              <Heart className={cn(asset.is_favorite && "fill-current text-signal")} /> {asset.is_favorite ? "Favourite" : "Add to favourites"}
            </Button>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
          {asset.url && (
            <Button asChild variant="ghost" size="sm">
              <a href={asset.url} download={asset.original_filename ?? undefined} target="_blank" rel="noreferrer"><Download /> Open original</a>
            </Button>
          )}
          {canEdit &&
            (confirmDelete ? (
              <span className="ml-auto flex items-center gap-2 text-sm">
                Delete this file?
                <Button type="button" size="sm" variant="danger" onClick={() => remove.mutate()} loading={remove.isPending}>Delete</Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setConfirmDelete(false)}>Keep</Button>
              </span>
            ) : (
              <Button type="button" variant="ghost" size="sm" className="ml-auto text-signal" onClick={() => setConfirmDelete(true)}>
                <Trash2 /> Delete
              </Button>
            ))}
        </div>
      </form>
    </div>
  );
}

export function MediaDetail(props: {
  workspaceId: string;
  asset: MediaAsset | null;
  folders: MediaFolder[];
  tagSuggestions: string[];
  canEdit: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog open={!!props.asset} onOpenChange={(open) => !open && props.onClose()}>
      {props.asset && (
        <DialogContent title={props.asset.display_name} className="w-[min(60rem,calc(100vw-2rem))] max-h-[92vh] overflow-y-auto">
          {/* key: reset the form when switching assets */}
          <Editor key={props.asset.id} {...props} asset={props.asset} />
        </DialogContent>
      )}
    </Dialog>
  );
}
