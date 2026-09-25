"use client";

import { useDeferredValue, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clapperboard, FolderPlus, Heart, ImageIcon, Images, Inbox, Search, Sparkles, Upload } from "lucide-react";
import { PageTitle } from "@/components/app/page-title";
import { useSession } from "@/components/app/session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { mediaApi, type MediaQuery } from "@/lib/api/endpoints";
import { ACCEPT } from "@/lib/uploads";
import { cn } from "@/lib/utils";
import type { MediaAsset } from "@/types/api";
import { BuildVideoDialog, GenerateImageDialog } from "./create-dialogs";
import { MediaDetail } from "./media-detail";
import { MediaTile } from "./media-tile";
import { UploadTray } from "./upload-tray";
import { useUploader } from "./use-uploader";

type View = { kind: "all" } | { kind: "favorites" } | { kind: "unfiled" } | { kind: "folder"; id: string };

function FolderButton({ active, onClick, icon: Icon, label, count }: { active: boolean; onClick: () => void; icon: typeof Images; label: string; count?: number }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "true" : undefined}
      className={cn("flex w-full items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-left text-sm text-muted hover:bg-sunk hover:text-ink", active && "bg-surface font-medium text-ink ring-1 ring-line")}
    >
      <Icon className={cn("size-4 shrink-0", active && "text-lab")} aria-hidden />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {count !== undefined && <span className="numeric text-xs text-faint">{count}</span>}
    </button>
  );
}

export function MediaLibrary() {
  const { workspace } = useSession();
  const ws = workspace.id;
  const canEdit = workspace.role !== "viewer";
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const [view, setView] = useState<View>({ kind: "all" });
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<"" | "image" | "video">("");
  const [tag, setTag] = useState("");
  const [open, setOpen] = useState<MediaAsset | null>(null);
  const [dragging, setDragging] = useState(false);
  const [newFolder, setNewFolder] = useState<string | null>(null);
  const [creating, setCreating] = useState<null | "image" | "video">(null);
  const [notice, setNotice] = useState<string | null>(null);
  const q = useDeferredValue(search.trim());

  const folderId = view.kind === "folder" ? view.id : null;
  const uploader = useUploader(ws, { folderId });

  const filters: MediaQuery = {
    q: q || undefined,
    kind: kind || undefined,
    tag: tag || undefined,
    favorites: view.kind === "favorites",
    folder: view.kind === "folder" ? view.id : view.kind === "unfiled" ? "unfiled" : undefined,
  };

  const media = useInfiniteQuery({
    queryKey: ["media", ws, filters],
    queryFn: ({ pageParam }) => mediaApi.list(ws, { ...filters, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    // Keep polling while anything is still being processed by the worker.
    refetchInterval: (query) =>
      query.state.data?.pages.some((p) => p.items.some((i) => i.status === "processing")) ? 1500 : false,
  });
  const folders = useQuery({ queryKey: ["media-folders", ws], queryFn: () => mediaApi.folders(ws) });
  const tags = useQuery({ queryKey: ["media-tags", ws], queryFn: () => mediaApi.tags(ws) });

  const createFolder = useMutation({
    mutationFn: (name: string) => mediaApi.createFolder(ws, name),
    onSuccess: (f) => {
      setNewFolder(null);
      setView({ kind: "folder", id: f.id });
      void queryClient.invalidateQueries({ queryKey: ["media-folders", ws] });
    },
  });
  const deleteFolder = useMutation({
    mutationFn: (id: string) => mediaApi.deleteFolder(ws, id),
    onSuccess: () => {
      setView({ kind: "all" });
      void queryClient.invalidateQueries({ queryKey: ["media-folders", ws] });
      void queryClient.invalidateQueries({ queryKey: ["media", ws] });
    },
  });

  const items = media.data?.pages.flatMap((p) => p.items) ?? [];
  const total = media.data?.pages[0]?.total ?? 0;
  const filtered = !!(q || kind || tag || view.kind !== "all");
  const currentFolder = folders.data?.find((f) => view.kind === "folder" && f.id === view.id);
  // Keep the open dialog in sync with refreshed data (status/processing changes, edits).
  const openAsset = open ? (items.find((i) => i.id === open.id) ?? open) : null;

  return (
    <div
      className="relative mx-auto max-w-7xl"
      onDragEnter={(e) => {
        if (canEdit && e.dataTransfer.types.includes("Files")) setDragging(true);
      }}
      onDragOver={(e) => canEdit && e.preventDefault()}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (canEdit && e.dataTransfer.files.length) void uploader.add(e.dataTransfer.files);
      }}
    >
      <PageTitle
        title="Media"
        description="Your photos and videos. Your agent uses these first when they fit a post."
        actions={
          canEdit && (
            <>
              <input ref={fileInput} type="file" accept={ACCEPT} multiple hidden onChange={(e) => { if (e.target.files?.length) void uploader.add(e.target.files); e.target.value = ""; }} />
              <Button variant="secondary" onClick={() => setCreating("image")}><Sparkles /> Generate image</Button>
              <Button variant="secondary" onClick={() => setCreating("video")}><Clapperboard /> Build video</Button>
              <Button onClick={() => fileInput.current?.click()}><Upload /> Upload</Button>
            </>
          )
        }
      />

      <div className="grid gap-6 lg:grid-cols-[13rem_1fr]">
        <nav aria-label="Folders" className="grid content-start gap-0.5">
          <FolderButton icon={Images} label="All media" active={view.kind === "all"} onClick={() => setView({ kind: "all" })} />
          <FolderButton icon={Heart} label="Favourites" active={view.kind === "favorites"} onClick={() => setView({ kind: "favorites" })} />
          <FolderButton icon={Inbox} label="Unfiled" active={view.kind === "unfiled"} onClick={() => setView({ kind: "unfiled" })} />
          <div className="my-2 h-px bg-line" />
          {folders.data?.map((f) => (
            <FolderButton key={f.id} icon={ImageIcon} label={f.name} count={f.asset_count} active={view.kind === "folder" && view.id === f.id} onClick={() => setView({ kind: "folder", id: f.id })} />
          ))}
          {canEdit &&
            (newFolder === null ? (
              <button type="button" onClick={() => setNewFolder("")} className="flex items-center gap-2.5 px-3 py-2 text-sm text-lab hover:underline">
                <FolderPlus className="size-4" aria-hidden /> New folder
              </button>
            ) : (
              <form
                className="grid gap-2 px-1 pt-1"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (newFolder.trim()) createFolder.mutate(newFolder.trim());
                }}
              >
                <Input autoFocus value={newFolder} onChange={(e) => setNewFolder(e.target.value)} placeholder="Folder name" maxLength={120} className="h-9" aria-label="Folder name" onKeyDown={(e) => e.key === "Escape" && setNewFolder(null)} />
                {createFolder.error && <p className="text-xs text-signal">{createFolder.error instanceof ApiError ? createFolder.error.message : "Folder not created."}</p>}
                <div className="flex gap-2">
                  <Button type="submit" size="sm" loading={createFolder.isPending}>Create</Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setNewFolder(null)}>Cancel</Button>
                </div>
              </form>
            ))}
        </nav>

        <section aria-label="Library" className="grid content-start gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <label className="relative min-w-56 flex-1">
              <span className="sr-only">Search media</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" aria-hidden />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search names, descriptions and tags" className="pl-9" />
            </label>
            <div role="radiogroup" aria-label="Type" className="inline-flex rounded-[var(--radius-control)] bg-sunk p-1 text-sm">
              {(["", "image", "video"] as const).map((k) => (
                <button key={k || "all"} type="button" role="radio" aria-checked={kind === k} onClick={() => setKind(k)} className={cn("rounded-[7px] px-3 py-1.5 text-muted", kind === k && "bg-surface font-medium text-ink shadow-sm")}>
                  {k === "" ? "All" : k === "image" ? "Photos" : "Videos"}
                </button>
              ))}
            </div>
          </div>

          {!!tags.data?.length && (
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by tag">
              {tags.data.slice(0, 16).map((t) => (
                <button key={t.tag} type="button" aria-pressed={tag === t.tag} onClick={() => setTag(tag === t.tag ? "" : t.tag)} className={cn("rounded-full px-2.5 py-1 text-xs ring-1 ring-line hover:bg-sunk", tag === t.tag ? "bg-lab text-on-lab ring-lab hover:bg-lab-strong" : "text-muted")}>
                  {t.tag} <span className="numeric opacity-70">{t.count}</span>
                </button>
              ))}
            </div>
          )}

          {view.kind === "folder" && currentFolder && canEdit && (
            <div className="flex items-center justify-between gap-3 text-sm text-muted">
              <span>{currentFolder.name}: {currentFolder.asset_count} {currentFolder.asset_count === 1 ? "file" : "files"}</span>
              <button type="button" className="text-signal hover:underline" onClick={() => deleteFolder.mutate(currentFolder.id)}>Delete folder (keeps the files)</button>
            </div>
          )}

          {notice && <Alert tone="info" title={notice}><button className="underline" onClick={() => setNotice(null)}>Dismiss</button></Alert>}
          {media.isPending ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5" aria-busy="true">
              {Array.from({ length: 10 }, (_, i) => <Skeleton key={i} className="aspect-square rounded-[var(--radius-card)]" />)}
            </div>
          ) : media.error ? (
            <Alert tone="error" title="Your library didn't load">
              {media.error instanceof ApiError ? media.error.message : "Try again."} <button className="underline" onClick={() => void media.refetch()}>Retry</button>
            </Alert>
          ) : items.length === 0 ? (
            filtered ? (
              <p className="rounded-[var(--radius-card)] border border-dashed border-line-strong px-6 py-12 text-center text-muted">Nothing matches these filters.</p>
            ) : (
              <div className="grid justify-items-start gap-4 rounded-[var(--radius-card)] border border-dashed border-line-strong bg-surface/60 px-6 py-12 sm:px-10">
                <h2 className="text-lg font-semibold">Add your own photos and videos</h2>
                <p className="max-w-lg text-muted">
                  Products, your space, your team, behind the scenes. Real photos build trust, and your agent will choose from them before generating anything. Drag files here or upload them.
                </p>
                {canEdit && <Button onClick={() => fileInput.current?.click()}><Upload /> Upload files</Button>}
                <p className="text-sm text-faint">JPEG, PNG, WebP or GIF up to 25 MB. MP4, MOV or WebM up to 500 MB.</p>
              </div>
            )
          ) : (
            <>
              <p className="text-sm text-muted" role="status">{total} {total === 1 ? "file" : "files"}</p>
              <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
                {items.map((a) => (
                  <li key={a.id}><MediaTile asset={a} onOpen={() => setOpen(a)} /></li>
                ))}
              </ul>
              {media.hasNextPage && (
                <div><Button variant="secondary" onClick={() => void media.fetchNextPage()} loading={media.isFetchingNextPage}>Load more</Button></div>
              )}
            </>
          )}
        </section>
      </div>

      {dragging && (
        <div className="pointer-events-none fixed inset-0 z-50 grid place-items-center bg-[rgb(8_20_22/45%)] backdrop-blur-[1px]">
          <div className="rounded-[var(--radius-frame)] bg-surface px-10 py-8 text-center shadow-[var(--shadow-frame)]">
            <Upload className="mx-auto mb-3 size-6 text-lab" aria-hidden />
            <p className="font-semibold">Drop to upload{currentFolder ? ` to ${currentFolder.name}` : ""}</p>
          </div>
        </div>
      )}

      <MediaDetail
        workspaceId={ws}
        asset={openAsset}
        folders={folders.data ?? []}
        tagSuggestions={tags.data?.map((t) => t.tag) ?? []}
        canEdit={canEdit}
        onClose={() => setOpen(null)}
      />
      <UploadTray items={uploader.items} onCancel={uploader.cancel} onClear={uploader.clearFinished} />
      <GenerateImageDialog ws={ws} open={creating === "image"} onOpenChange={(o) => setCreating(o ? "image" : null)}
        onCreated={(_, reused) => setNotice(reused ? "You already had this exact image, so we reused it. Nothing was charged." : "Generating your image. It appears here when it's ready.")} />
      <BuildVideoDialog ws={ws} open={creating === "video"} onOpenChange={(o) => setCreating(o ? "video" : null)}
        onCreated={(_, reused) => setNotice(reused ? "You already built this exact video, so we reused it. Nothing was charged." : "Building your video. It appears here when it's ready.")} />
    </div>
  );
}
