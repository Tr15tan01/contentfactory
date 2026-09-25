"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, Check, Clapperboard, Copy, History, ImagePlus, Loader2, RefreshCw, Send, Sparkles, Trash2, X } from "lucide-react";
import { contentTypeName, StatusChip } from "@/components/common/status";
import { useSession } from "@/components/app/session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ChipsInput } from "@/components/ui/chips-input";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { contentApi, socialApi } from "@/lib/api/endpoints";
import { formatInZone, fromLocalInput, toLocalInput } from "@/lib/zoned";
import { cn } from "@/lib/utils";
import type { Content, ContentVariant, PlatformId } from "@/types/api";
import { MediaPicker } from "../business/media-picker";
import { BuildVideoDialog, GenerateImageDialog } from "../media/create-dialogs";
import { PILLAR_LABELS, PLATFORM_RULES } from "./meta";

const errText = (e: unknown) => (e instanceof ApiError ? (Object.values(e.fields)[0] ?? e.message) : "Something went wrong. Try again.");

function Preview({ content, variant, business }: { content: Content; variant: ContentVariant; business: string }) {
  const [more, setMore] = useState(false);
  const cover = content.media[0];
  const text = variant.caption || content.hook || "";
  const short = text.length > 140 && !more;
  return (
    <figure className="overflow-hidden rounded-[var(--radius-card)] bg-surface ring-1 ring-line" aria-label={`${PLATFORM_RULES[variant.platform].label} preview`}>
      <div className="flex items-center gap-2 px-3 py-2.5">
        <span className="grid size-7 place-items-center rounded-full bg-lab-soft text-[0.625rem] font-semibold text-lab">{business.slice(0, 2).toUpperCase()}</span>
        <span className="text-sm font-semibold">{business}</span>
        <span className="ml-auto text-xs text-muted">{PLATFORM_RULES[variant.platform].label}</span>
      </div>
      <div className="aspect-[4/5] bg-sunk">
        {cover?.thumbnail_url || (cover?.kind === "image" && cover.url) ? (
          // eslint-disable-next-line @next/next/no-img-element -- signed storage URL
          <img src={cover.thumbnail_url ?? cover.url ?? ""} alt="" className="size-full object-cover" />
        ) : (
          <div className="grid size-full place-items-center p-6 text-center text-sm text-muted">{content.visual_concept ?? "No visual yet"}</div>
        )}
      </div>
      <figcaption className="grid gap-1.5 px-3 py-3 text-sm">
        <p className="whitespace-pre-line">
          {short ? `${text.slice(0, 140)}… ` : `${text} `}
          {short && <button type="button" className="text-muted" onClick={() => setMore(true)}>more</button>}
        </p>
        {variant.cta && !text.includes(variant.cta) && <p className="font-medium">{variant.cta}</p>}
        {variant.hashtags.length > 0 && <p className="text-lab">{variant.hashtags.map((t) => `#${t}`).join(" ")}</p>}
      </figcaption>
    </figure>
  );
}

function Publications({ ws, content, canEdit, onChange }: { ws: string; content: Content; canEdit: boolean; onChange: (c: Content) => void }) {
  const retry = useMutation({
    mutationFn: async (id: string) => {
      await socialApi.retry(ws, id);
      return contentApi.get(ws, content.id);
    },
    onSuccess: onChange,
  });
  const label: Record<string, string> = { queued: "Waiting", publishing: "Publishing", published: "Published", failed: "Failed", cancelled: "Cancelled" };
  return (
    <section aria-label="Publishing" className="grid gap-2 rounded-[var(--radius-card)] bg-surface p-4 ring-1 ring-line">
      <h2 className="text-sm font-semibold">Publishing</h2>
      {retry.error && <Alert tone="error" title="Not retried">{errText(retry.error)}</Alert>}
      <ul className="grid gap-2">
        {content.publications.map((p) => (
          <li key={p.id} className="flex flex-wrap items-start gap-3 text-sm">
            <span className="w-24 shrink-0 font-medium">{PLATFORM_RULES[p.platform].label}</span>
            <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", p.status === "published" ? "bg-lab-soft text-lab" : p.status === "failed" ? "bg-signal-soft text-signal" : "bg-sunk text-muted")}>{label[p.status]}</span>
            <span className="min-w-0 flex-1 text-muted">
              {p.status === "published" && p.platform_url ? <a href={p.platform_url} target="_blank" rel="noreferrer" className="text-lab underline">View post</a> : null}
              {p.status === "queued" && p.next_retry_at ? `Retrying at ${new Date(p.next_retry_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}. ${p.error_message ?? ""}` : null}
              {p.status === "failed" ? p.error_message : null}
            </span>
            {p.status === "failed" && canEdit && <Button size="sm" variant="secondary" onClick={() => retry.mutate(p.id)} loading={retry.isPending && retry.variables === p.id}><RefreshCw /> Retry</Button>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Versions({ ws, id, onRestore }: { ws: string; id: string; onRestore: (v: number) => void }) {
  const versions = useQuery({ queryKey: ["content-versions", ws, id], queryFn: () => contentApi.versions(ws, id) });
  if (!versions.data?.length) return <p className="text-sm text-muted">No earlier versions yet.</p>;
  const reasons: Record<string, string> = { edit: "Before edit", regenerate: "Before redraft", restore: "Before restore" };
  return (
    <ol className="grid gap-2">
      {versions.data.map((v) => (
        <li key={v.version} className="flex items-start gap-3 text-sm">
          <span className="numeric w-7 shrink-0 text-muted">v{v.version}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate">{v.hook || v.title}</span>
            <span className="text-xs text-muted">{reasons[v.reason] ?? v.reason}, {new Date(v.created_at).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}{v.created_by ? `, ${v.created_by}` : ""}</span>
          </span>
          <Button size="sm" variant="ghost" onClick={() => onRestore(v.version)}>Restore</Button>
        </li>
      ))}
    </ol>
  );
}

function Editor({ content }: { content: Content }) {
  const { workspace } = useSession();
  const ws = workspace.id;
  const tz = workspace.timezone;
  const router = useRouter();
  const queryClient = useQueryClient();
  const canAct = workspace.role !== "viewer";
  // Posts that are going out or already out can't be changed (the server enforces this too).
  const locked = content.status === "published" || content.status === "publishing";
  const canEdit = canAct && !locked;

  const [title, setTitle] = useState(content.title);
  const [hook, setHook] = useState(content.hook ?? "");
  const [variants, setVariants] = useState<ContentVariant[]>(content.variants);
  const [mediaIds, setMediaIds] = useState(content.media.map((m) => m.id));
  const [tab, setTab] = useState<PlatformId>(content.variants[0]?.platform ?? "instagram");
  const [picking, setPicking] = useState(false);
  const [creating, setCreating] = useState<null | "image" | "video">(null);
  const [created, setCreated] = useState<string | null>(null);
  const [dialog, setDialog] = useState<null | "schedule" | "reject" | "regenerate" | "delete" | "history">(null);
  const [when, setWhen] = useState(content.schedule ? toLocalInput(content.schedule.scheduled_at, tz) : "");
  const [reason, setReason] = useState("");
  const [instruction, setInstruction] = useState("");

  const dirty =
    title !== content.title || hook !== (content.hook ?? "") ||
    JSON.stringify(variants) !== JSON.stringify(content.variants) ||
    JSON.stringify(mediaIds) !== JSON.stringify(content.media.map((m) => m.id));

  const apply = (c: Content) => {
    queryClient.setQueryData(["content-item", ws, c.id], c);
    void queryClient.invalidateQueries({ queryKey: ["content", ws] });
    void queryClient.invalidateQueries({ queryKey: ["content-versions", ws, c.id] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard", ws] });
    void queryClient.invalidateQueries({ queryKey: ["usage", ws] });
    setDialog(null);
  };
  const act = useMutation({ mutationFn: (fn: () => Promise<Content>) => fn(), onSuccess: apply });
  const save = () => contentApi.update(ws, content.id, { title, hook, variants, media_ids: mediaIds });
  const remove = useMutation({ mutationFn: () => contentApi.remove(ws, content.id), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["content", ws] }); router.push("/content"); } });
  const duplicate = useMutation({ mutationFn: () => contentApi.duplicate(ws, content.id), onSuccess: (c) => { void queryClient.invalidateQueries({ queryKey: ["content", ws] }); router.push(`/content/${c.id}`); } });

  const variant = variants.find((v) => v.platform === tab) ?? variants[0];
  const setVariant = (patch: Partial<ContentVariant>) => setVariants((vs) => vs.map((v) => (v.platform === variant?.platform ? { ...v, ...patch } : v)));
  const rules = variant ? PLATFORM_RULES[variant.platform] : null;
  const s = content.status;
  const needsApproval = s === "awaiting_approval" || s === "ready" || s === "draft" || s === "rejected";

  return (
    <div className="mx-auto grid max-w-6xl gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid min-w-0 flex-1 gap-2">
          <Link href="/content" className="text-sm text-muted hover:text-ink">Content</Link>
          <input value={title} onChange={(e) => setTitle(e.target.value)} disabled={!canEdit} aria-label="Title" maxLength={200} className="display w-full bg-transparent text-3xl outline-none focus-visible:underline sm:text-4xl" />
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <StatusChip status={s} />
            <span>{contentTypeName(content.content_type)}</span>
            {content.pillar && <span>{PILLAR_LABELS[content.pillar] ?? content.pillar}</span>}
            {content.schedule && (
              <span className="inline-flex items-center gap-1.5"><CalendarClock className="size-4" aria-hidden />{formatInZone(content.schedule.scheduled_at, tz, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span>
            )}
          </div>
        </div>
        {canEdit && (
          <div className="flex flex-wrap gap-2">
            {dirty ? (
              <>
                <Button onClick={() => act.mutate(save)} loading={act.isPending}>Save changes</Button>
                <Button variant="ghost" onClick={() => { setTitle(content.title); setHook(content.hook ?? ""); setVariants(content.variants); setMediaIds(content.media.map((m) => m.id)); }}>Discard</Button>
              </>
            ) : (
              <>
                {needsApproval && <Button onClick={() => act.mutate(() => contentApi.approve(ws, content.id))} loading={act.isPending}><Check /> Approve</Button>}
                {(s === "ready" || s === "draft" || s === "rejected") && <Button variant="secondary" onClick={() => act.mutate(() => contentApi.submit(ws, content.id))}><Send /> Send for approval</Button>}
                {(s === "awaiting_approval" || s === "approved" || s === "scheduled") && <Button variant="secondary" onClick={() => setDialog("reject")}><X /> Reject</Button>}
                <Button variant="secondary" onClick={() => setDialog("schedule")}><CalendarClock /> {content.schedule ? "Reschedule" : "Schedule"}</Button>
              </>
            )}
          </div>
        )}
      </div>

      {act.error && <Alert tone="error" title="That didn't work">{errText(act.error)}</Alert>}
      {s === "rejected" && content.rejected_reason && <Alert tone="info" title="Rejected">{content.rejected_reason}</Alert>}
      {content.missing_accounts.length > 0 && !["published"].includes(s) && (
        <Alert tone="error" title={`No ${content.missing_accounts.map((p) => PLATFORM_RULES[p].label).join(" or ")} account connected`}>
          This post can&apos;t publish there until you <Link href="/settings/social">connect an account</Link>.
        </Alert>
      )}
      {s === "scheduled" && content.schedule && content.missing_accounts.length === 0 && (
        <Alert tone="success" title="Scheduled">
          Publishes automatically on {formatInZone(content.schedule.scheduled_at, tz, { weekday: "long", month: "long", day: "numeric", hour: "numeric", minute: "2-digit" })}.
        </Alert>
      )}
      {s === "approved" && !content.schedule && <Alert tone="info" title="Approved">Pick a time to schedule it.</Alert>}
      {content.publications.length > 0 && <Publications ws={ws} content={content} canEdit={canAct} onChange={apply} />}
      {content.warnings.length > 0 && (
        <ul className="grid gap-1.5 rounded-[var(--radius-card)] bg-caution-soft px-4 py-3 text-sm">
          {content.warnings.map((w) => (
            <li key={w.code + w.message} className="flex gap-2"><AlertTriangle className="mt-0.5 size-4 shrink-0 text-caution" aria-hidden />{w.message}</li>
          ))}
        </ul>
      )}

      <div className="grid items-start gap-8 lg:grid-cols-[1fr_20rem]">
        <div className="grid gap-6">
          <Field id="hook" label="Hook" hint="The first line people see.">
            <Input value={hook} onChange={(e) => setHook(e.target.value)} maxLength={1000} disabled={!canEdit} />
          </Field>

          <div className="grid gap-4">
            <div role="tablist" aria-label="Platforms" className="flex gap-1 border-b border-line">
              {variants.map((v) => (
                <button key={v.platform} role="tab" aria-selected={tab === v.platform} onClick={() => setTab(v.platform)} className={cn("-mb-px border-b-2 border-transparent px-3 pb-2.5 text-sm text-muted", tab === v.platform && "border-lab font-medium text-ink")}>
                  {PLATFORM_RULES[v.platform].label}
                </button>
              ))}
            </div>
            {variant && rules && (
              <div className="grid gap-5" role="tabpanel">
                <Field id="caption" label="Caption" hint={<span className={cn("numeric", variant.caption.length > rules.captionMax && "text-signal")}>{variant.caption.length} / {rules.captionMax}</span>}>
                  <Textarea value={variant.caption} onChange={(e) => setVariant({ caption: e.target.value })} rows={9} disabled={!canEdit} />
                </Field>
                <Field id="hashtags" label="Hashtags" hint={`${variant.hashtags.length} / ${rules.hashtagsMax}`}>
                  <ChipsInput value={variant.hashtags} onChange={(v) => setVariant({ hashtags: v })} max={rules.hashtagsMax} normalize={(t) => t.trim().replace(/^#/, "").replace(/\s+/g, "")} />
                </Field>
                <Field id="cta" label="Call to action">
                  <Input value={variant.cta ?? ""} onChange={(e) => setVariant({ cta: e.target.value })} maxLength={300} disabled={!canEdit} />
                </Field>
              </div>
            )}
          </div>

          <div className="grid gap-3">
            <p className="text-sm font-medium">Media</p>
            <div className="flex flex-wrap items-center gap-2">
              {content.media.filter((m) => mediaIds.includes(m.id)).map((m) => (
                <span key={m.id} className="relative">
                  {/* eslint-disable-next-line @next/next/no-img-element -- signed storage URL */}
                  {m.thumbnail_url ? <img src={m.thumbnail_url} alt={m.display_name} className="size-20 rounded-md object-cover" /> : <span className="grid size-20 place-items-center rounded-md bg-sunk text-xs text-muted">{m.kind}</span>}
                  {canEdit && <button type="button" onClick={() => setMediaIds(mediaIds.filter((x) => x !== m.id))} className="absolute -right-1.5 -top-1.5 grid size-5 place-items-center rounded-full bg-ink text-paper" aria-label={`Remove ${m.display_name}`}><X className="size-3" /></button>}
                </span>
              ))}
              {mediaIds.some((id) => !content.media.find((m) => m.id === id)) && <span className="text-sm text-muted">New selection, save to see it</span>}
              {canEdit && <Button type="button" variant="secondary" size="sm" onClick={() => setPicking(true)}><ImagePlus /> Choose media</Button>}
              {canEdit && !dirty && <Button type="button" variant="ghost" size="sm" onClick={() => setCreating("image")}><Sparkles /> Generate image</Button>}
              {canEdit && !dirty && (content.script || ["reel", "short", "story", "video"].includes(content.content_type)) && (
                <Button type="button" variant="ghost" size="sm" onClick={() => setCreating("video")}><Clapperboard /> {content.script ? "Build video from script" : "Build video"}</Button>
              )}
            </div>
            {created && <p className="text-sm text-muted" role="status">{created}</p>}
            {content.visual_concept && <p className="text-sm text-muted"><span className="font-medium text-ink">Visual idea:</span> {content.visual_concept}</p>}
          </div>
          <GenerateImageDialog ws={ws} open={creating === "image"} onOpenChange={(o) => setCreating(o ? "image" : null)} contentId={content.id}
            initialPrompt={content.image_prompt ?? content.visual_concept ?? content.title}
            onCreated={(_, reused) => setCreated(reused ? "Reused an identical image you already had, and added it. No charge." : "Generating. The image is added to this post when it's ready.")} />
          <BuildVideoDialog ws={ws} open={creating === "video"} onOpenChange={(o) => setCreating(o ? "video" : null)} contentId={content.id} title={content.title}
            initialScenes={content.script?.map((sc) => ({ text: sc.on_screen_text ?? "", duration: sc.duration_s ?? 3 }))}
            onCreated={(_, reused) => setCreated(reused ? "Reused an identical video you already built, and added it. No charge." : "Building. The video is added to this post when it's ready.")} />
          <MediaPicker workspaceId={ws} open={picking} onOpenChange={setPicking} kind="any" selected={mediaIds} onConfirm={(ids) => setMediaIds(ids)} />

          {content.script && (
            <section className="grid gap-2">
              <h2 className="text-sm font-medium">Video script</h2>
              <ol className="grid gap-2 text-sm">
                {content.script.map((sc, i) => (
                  <li key={i} className="grid grid-cols-[3rem_1fr] gap-3 rounded-md bg-sunk/60 px-3 py-2">
                    <span className="numeric text-muted">{sc.duration_s ? `${sc.duration_s}s` : `#${i + 1}`}</span>
                    <span>{sc.scene}{sc.on_screen_text ? <span className="block text-muted">On screen: {sc.on_screen_text}</span> : null}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}
          {content.slides && (
            <section className="grid gap-2">
              <h2 className="text-sm font-medium">Carousel slides</h2>
              <ol className="grid gap-2 sm:grid-cols-2">
                {content.slides.map((sl, i) => (
                  <li key={i} className="rounded-md bg-sunk/60 px-3 py-2 text-sm"><span className="numeric text-muted">{i + 1}.</span> <span className="font-medium">{sl.heading}</span><span className="block text-muted">{sl.text}</span></li>
                ))}
              </ol>
            </section>
          )}
        </div>

        <aside className="grid gap-4 lg:sticky lg:top-20">
          {variant && <Preview content={content} variant={variant} business={workspace.name} />}
          {canAct && (
            <div className="flex flex-wrap gap-2">
              {canEdit && <Button size="sm" variant="secondary" onClick={() => setDialog("regenerate")}><RefreshCw /> Redraft</Button>}
              <Button size="sm" variant="ghost" onClick={() => duplicate.mutate()} loading={duplicate.isPending}><Copy /> Duplicate</Button>
              {canEdit && <Button size="sm" variant="ghost" onClick={() => setDialog("history")}><History /> History</Button>}
              {content.status !== "publishing" && <Button size="sm" variant="ghost" className="text-signal" onClick={() => setDialog("delete")}><Trash2 /> Delete</Button>}
            </div>
          )}
          {locked && <p className="text-xs text-muted">{content.status === "published" ? "Published posts can't be edited here. Duplicate it to make a new version." : "This post is being published."}</p>}
          <p className="text-xs text-muted">
            {content.generation.provider === "mock"
              ? "Drafted by the offline test writer (development mode)."
              : content.generation.model ? `Drafted with ${content.generation.model}${content.generation.cached ? " (reused, not charged)" : ""}.` : "Written by hand."}{" "}
            Version {content.version}.
          </p>
        </aside>
      </div>

      <Dialog open={dialog !== null} onOpenChange={(o) => !o && setDialog(null)}>
        {dialog === "schedule" && (
          <DialogContent title={content.schedule ? "Reschedule post" : "Schedule post"} description={`Time zone: ${tz.replaceAll("_", " ")}. ${needsApproval ? "It still needs approval before it can go out." : ""}`}>
            <form className="mt-5 grid gap-4" onSubmit={(e) => { e.preventDefault(); act.mutate(() => contentApi.schedule(ws, content.id, fromLocalInput(when, tz))); }}>
              {act.error && <Alert tone="error" title="Not scheduled">{errText(act.error)}</Alert>}
              <Input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
              <div className="flex justify-end gap-2">
                {content.schedule && <Button type="button" variant="ghost" onClick={() => act.mutate(() => contentApi.unschedule(ws, content.id))}>Remove from calendar</Button>}
                <Button type="submit" loading={act.isPending}>Save</Button>
              </div>
            </form>
          </DialogContent>
        )}
        {dialog === "reject" && (
          <DialogContent title="Reject this post?" description="Tell your agent (and your team) what was wrong. It stays in Content so you can fix it.">
            <form className="mt-5 grid gap-4" onSubmit={(e) => { e.preventDefault(); act.mutate(() => contentApi.reject(ws, content.id, reason)); }}>
              <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Too salesy, wrong product, photo doesn't fit…" maxLength={1000} rows={3} className="min-h-24" />
              <div className="flex justify-end"><Button type="submit" loading={act.isPending}>Reject</Button></div>
            </form>
          </DialogContent>
        )}
        {dialog === "regenerate" && (
          <DialogContent title="Redraft with AI" description="Uses one AI draft from your monthly allowance. The current version is saved in History.">
            <form className="mt-5 grid gap-4" onSubmit={(e) => { e.preventDefault(); act.mutate(() => contentApi.regenerate(ws, content.id, instruction)); }}>
              {act.error && <Alert tone="error" title="Not redrafted">{errText(act.error)}</Alert>}
              <Textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Optional: shorter, more playful, mention the weekend opening hours…" maxLength={500} rows={3} className="min-h-24" />
              <div className="flex justify-end"><Button type="submit" loading={act.isPending}><RefreshCw /> Redraft</Button></div>
            </form>
          </DialogContent>
        )}
        {dialog === "delete" && (
          <DialogContent title="Delete this post?" description="It will be removed from Content and the calendar.">
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDialog(null)}>Keep</Button>
              <Button variant="danger" onClick={() => remove.mutate()} loading={remove.isPending}>Delete</Button>
            </div>
          </DialogContent>
        )}
        {dialog === "history" && (
          <DialogContent title="Version history" description="Restoring creates a new version; nothing is lost.">
            <div className="mt-5 max-h-[60vh] overflow-y-auto"><Versions ws={ws} id={content.id} onRestore={(v) => act.mutate(() => contentApi.restore(ws, content.id, v))} /></div>
          </DialogContent>
        )}
      </Dialog>
    </div>
  );
}

export function PostEditor({ id }: { id: string }) {
  const { workspace } = useSession();
  const post = useQuery({
    queryKey: ["content-item", workspace.id, id],
    queryFn: () => contentApi.get(workspace.id, id),
    refetchInterval: (q) => {
      const d = q.state.data;
      if (d?.status === "generating") return 1500;
      if (d?.status === "publishing") return 5000;
      // Due within two minutes (or overdue): watch it go out.
      if (d?.status === "scheduled" && d.schedule && new Date(d.schedule.scheduled_at).getTime() - Date.now() < 120_000) return 10_000;
      return false;
    },
  });
  const queryClient = useQueryClient();

  if (post.isPending) return <div className="mx-auto grid max-w-6xl gap-4"><Skeleton className="h-10 w-80" /><Skeleton className="h-64" /></div>;
  if (post.error || !post.data) {
    return <div className="mx-auto max-w-2xl"><Alert tone="error" title="Post not found">{post.error instanceof ApiError && post.error.status === 404 ? "It may have been deleted." : errText(post.error)} <Link href="/content">Back to Content</Link></Alert></div>;
  }
  const c = post.data;
  if (c.status === "generating") {
    return (
      <div className="mx-auto grid max-w-2xl justify-items-center gap-4 py-24 text-center" role="status">
        <Loader2 className="size-6 animate-spin text-lab" aria-hidden />
        <h1 className="display text-3xl">Your agent is writing</h1>
        <p className="text-muted">Using your business profile, brand voice{c.product_id ? ", the product you picked" : ""} and media library. This usually takes a few seconds.</p>
      </div>
    );
  }
  if (c.status === "failed" && c.generation.error) {
    return (
      <div className="mx-auto grid max-w-2xl gap-4 py-16">
        <Alert tone="error" title="The draft didn't finish">{c.generation.error}</Alert>
        <div className="flex gap-2">
          <Button onClick={async () => { const next = await contentApi.regenerate(workspace.id, c.id); queryClient.setQueryData(["content-item", workspace.id, c.id], next); }}><RefreshCw /> Try again</Button>
          <Button asChild variant="ghost"><Link href="/content">Back to Content</Link></Button>
        </div>
      </div>
    );
  }
  // key: reset local edits when the server version changes (save, approve, restore).
  return <Editor key={`${c.id}-${c.version}-${c.status}-${c.updated_at}`} content={c} />;
}
