"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ImagePlus, PenLine, Sparkles, X } from "lucide-react";
import { PageTitle } from "@/components/app/page-title";
import { useSession } from "@/components/app/session";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { contentApi } from "@/lib/api/endpoints";
import { fromLocalInput } from "@/lib/zoned";
import { cn } from "@/lib/utils";
import type { ContentType, MediaAsset, PlatformId } from "@/types/api";
import { FormError, Toggle, toggle } from "../business/form-bits";
import { MediaPicker } from "../business/media-picker";
import { GOALS } from "../business/options";
import { useBusiness } from "../business/use-business";
import { CONTENT_TYPES, PLATFORM_ORDER, PLATFORM_RULES } from "./meta";
import { UsageNote, useUsage } from "./usage-note";

export function NewPost() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { workspace } = useSession();
  const ws = workspace.id;
  const biz = useBusiness();
  const usage = useUsage(ws);

  const [mode, setMode] = useState<"ai" | "manual">("ai");
  const [idea, setIdea] = useState("");
  const [ctype, setCtype] = useState<ContentType>("post");
  const preferred = biz.data?.preferences.preferred_platforms.filter((p) => PLATFORM_RULES[p].available) ?? [];
  const [platforms, setPlatforms] = useState<PlatformId[] | null>(null);
  const chosen = platforms ?? (preferred.length ? preferred.filter((p) => PLATFORM_RULES[p].types.includes("post")) : ["instagram"]);
  const [goal, setGoal] = useState("");
  const [productId, setProductId] = useState("");
  const [media, setMedia] = useState<MediaAsset[]>([]);
  const [picking, setPicking] = useState(false);
  const [when, setWhen] = useState("");
  const [title, setTitle] = useState("");
  const [caption, setCaption] = useState("");

  const valid = chosen.filter((p) => PLATFORM_RULES[p].types.includes(ctype));
  const outOfDrafts = mode === "ai" && usage.data?.ai_content.remaining === 0;

  const create = useMutation({
    mutationFn: () => {
      const scheduled_at = when ? fromLocalInput(when, workspace.timezone) : null;
      if (mode === "ai") {
        return contentApi.generate(ws, {
          idea: idea.trim() || undefined, platforms: valid, content_type: ctype, goal: goal || null,
          product_id: productId || null, media_ids: media.map((m) => m.id), scheduled_at,
        });
      }
      return contentApi.create(ws, { title: title.trim() || "Untitled post", content_type: ctype, platforms: valid, caption, media_ids: media.map((m) => m.id) }).then(async (c) =>
        scheduled_at ? contentApi.schedule(ws, c.id, scheduled_at) : c,
      );
    },
    onSuccess: (c) => {
      void queryClient.invalidateQueries({ queryKey: ["usage", ws] });
      void queryClient.invalidateQueries({ queryKey: ["content", ws] });
      router.push(`/content/${c.id}`);
    },
  });

  return (
    <div className="mx-auto max-w-5xl">
      <PageTitle title="Create post" description="Describe the post you want, or leave it open and let your agent pick an angle from your business profile." />
      <div className="grid items-start gap-8 lg:grid-cols-[1fr_18rem]">
        <form className="grid gap-7" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div role="tablist" aria-label="How to create" className="inline-flex justify-self-start rounded-[var(--radius-control)] bg-sunk p-1 text-sm">
            {([["ai", "Draft with AI", Sparkles], ["manual", "Write it myself", PenLine]] as const).map(([id, label, Icon]) => (
              <button key={id} type="button" role="tab" aria-selected={mode === id} onClick={() => setMode(id)} className={cn("inline-flex items-center gap-2 rounded-[7px] px-3.5 py-1.5 text-muted", mode === id && "bg-surface font-medium text-ink shadow-sm")}>
                <Icon className="size-4" aria-hidden /> {label}
              </button>
            ))}
          </div>
          <FormError error={create.error} title="Post not created" />

          {mode === "ai" ? (
            <Field id="idea" label="What should this post be about?" hint="Optional. For example: why our cold brew takes 18 hours, or this week's new pastry.">
              <Textarea value={idea} onChange={(e) => setIdea(e.target.value)} maxLength={1000} rows={3} className="min-h-24" />
            </Field>
          ) : (
            <>
              <Field id="title" label="Title" hint="For your calendar. Not published.">
                <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required />
              </Field>
              <Field id="caption" label="Caption">
                <Textarea value={caption} onChange={(e) => setCaption(e.target.value)} rows={6} maxLength={10000} />
              </Field>
            </>
          )}

          <fieldset className="grid gap-3">
            <legend className="mb-1 text-sm font-medium">Format</legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              {CONTENT_TYPES.map((t) => (
                <Toggle key={t.id} pressed={ctype === t.id} onClick={() => setCtype(t.id)}>
                  <span className="block font-medium">{t.label}</span>
                  <span className="block text-xs text-muted">{t.hint}</span>
                </Toggle>
              ))}
            </div>
          </fieldset>

          <fieldset className="grid gap-3">
            <legend className="mb-1 text-sm font-medium">Platforms</legend>
            <div className="flex flex-wrap gap-2">
              {PLATFORM_ORDER.filter((p) => PLATFORM_RULES[p].available).map((p) => {
                const supported = PLATFORM_RULES[p].types.includes(ctype);
                return (
                  <Toggle key={p} pressed={supported && chosen.includes(p)} disabled={!supported} onClick={() => setPlatforms(toggle(chosen, p))} className="rounded-full px-4 py-1.5">
                    {PLATFORM_RULES[p].label}
                  </Toggle>
                );
              })}
            </div>
            {chosen.length > valid.length && <p className="text-sm text-muted">Some selected platforms don&apos;t support this format and will be skipped.</p>}
          </fieldset>

          {mode === "ai" && (
            <div className="grid gap-5 sm:grid-cols-2">
              <Field id="goal" label="Goal">
                <Select value={goal} onChange={(e) => setGoal(e.target.value)}>
                  <option value="">Let the agent decide</option>
                  {GOALS.map((g) => <option key={g.id} value={g.id}>{g.label}</option>)}
                </Select>
              </Field>
              <Field id="product" label="Feature a product">
                <Select value={productId} onChange={(e) => setProductId(e.target.value)}>
                  <option value="">None</option>
                  {biz.data?.products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </Select>
              </Field>
            </div>
          )}

          <div className="grid gap-2">
            <p className="text-sm font-medium">Photos and videos</p>
            <div className="flex flex-wrap items-center gap-2">
              {media.map((m) => (
                <span key={m.id} className="relative">
                  {/* eslint-disable-next-line @next/next/no-img-element -- signed storage URL */}
                  <img src={m.thumbnail_url ?? m.url ?? ""} alt={m.display_name} className="size-16 rounded-md object-cover" />
                  <button type="button" onClick={() => setMedia(media.filter((x) => x.id !== m.id))} className="absolute -right-1.5 -top-1.5 grid size-5 place-items-center rounded-full bg-ink text-paper" aria-label={`Remove ${m.display_name}`}><X className="size-3" /></button>
                </span>
              ))}
              <Button type="button" variant="secondary" size="sm" onClick={() => setPicking(true)}><ImagePlus /> {media.length ? "Change" : "Choose from library"}</Button>
            </div>
            {mode === "ai" && !media.length && <p className="text-sm text-muted">Leave empty and your agent will pick from your library ({biz.data?.preferences.prefer_media === "never" ? "turned off in your preferences" : "when something fits"}).</p>}
          </div>
          <MediaPicker workspaceId={ws} open={picking} onOpenChange={setPicking} kind="any" selected={media.map((m) => m.id)} onConfirm={(_, assets) => setMedia(assets)} />

          <Field id="when" label="Schedule" hint={`Optional. Times are in ${workspace.timezone.replaceAll("_", " ")}. Scheduled posts still need approval.`}>
            <Input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} className="sm:max-w-64" />
          </Field>

          <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
            <Button type="submit" size="lg" loading={create.isPending} disabled={!valid.length || outOfDrafts}>
              {mode === "ai" ? <><Sparkles /> Draft post</> : "Save draft"}
            </Button>
            {outOfDrafts && <p className="text-sm text-signal">No AI drafts left this month.</p>}
          </div>
        </form>
        <aside className="grid gap-4 lg:sticky lg:top-20">
          <UsageNote ws={ws} />
          <p className="text-xs text-muted">Your agent writes from your business profile, brand voice and products. It never invents prices, offers or facts you haven&apos;t given it, and nothing is posted without approval.</p>
        </aside>
      </div>
    </div>
  );
}
