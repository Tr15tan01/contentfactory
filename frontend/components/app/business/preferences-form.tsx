"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { businessApi } from "@/lib/api/endpoints";
import type { Business, PublishingPreferences } from "@/types/api";
import { FormActions, FormError, Toggle, toggle } from "./form-bits";
import { PLATFORMS } from "./options";
import { useBusiness } from "./use-business";

const MEDIA = [
  { id: "always", label: "Always", hint: "Only use my photos and videos" },
  { id: "when_relevant", label: "When relevant", hint: "Mine first, generate when nothing fits" },
  { id: "never", label: "Never", hint: "Always create new visuals" },
] as const;

const REMINDERS = [
  { hours: 24, label: "24 hours before" },
  { hours: 6, label: "6 hours before" },
  { hours: 1, label: "1 hour before" },
] as const;

export function PreferencesForm({ business, submitLabel, onSaved, secondary, only }: {
  business: Business;
  submitLabel: string;
  onSaved?: () => void;
  secondary?: React.ReactNode;
  /** Render just one part (onboarding splits media from publishing). */
  only?: "media" | "publishing";
}) {
  const { workspaceId, update, refresh } = useBusiness();
  const [p, setP] = useState<PublishingPreferences>(business.preferences);
  const set = <K extends keyof PublishingPreferences>(k: K, v: PublishingPreferences[K]) => setP((x) => ({ ...x, [k]: v }));
  const save = useMutation({
    mutationFn: () => businessApi.savePreferences(workspaceId, p),
    onSuccess: (preferences) => {
      update((b) => ({ ...b, preferences }));
      refresh();
      onSaved?.();
    },
  });

  return (
    <form className="grid gap-7" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <FormError error={save.error} />
      {only !== "publishing" && (
        <fieldset className="grid gap-3">
          <legend className="mb-1 text-sm font-medium">Prefer my own media</legend>
          <div className="grid gap-2 sm:grid-cols-3" role="radiogroup">
            {MEDIA.map((m) => (
              <Toggle key={m.id} pressed={p.prefer_media === m.id} onClick={() => set("prefer_media", m.id)}>
                <span className="block font-medium">{m.label}</span>
                <span className="block text-xs text-muted">{m.hint}</span>
              </Toggle>
            ))}
          </div>
        </fieldset>
      )}
      {only !== "media" && (
        <>
          <fieldset className="grid gap-3">
            <legend className="mb-1 text-sm font-medium">Where do you want to post?</legend>
            <div className="flex flex-wrap gap-2">
              {PLATFORMS.map((pl) => (
                <Toggle key={pl.id} pressed={p.preferred_platforms.includes(pl.id)} disabled={!pl.available} onClick={() => set("preferred_platforms", toggle(p.preferred_platforms, pl.id))} className="rounded-full px-4 py-1.5">
                  {pl.label}{!pl.available && " (planned)"}
                </Toggle>
              ))}
            </div>
            <p className="text-sm text-muted">You&apos;ll connect the accounts themselves in <Link href="/settings/social" className="text-lab underline">Social accounts</Link>. Nothing is posted until an account is connected.</p>
          </fieldset>
          <fieldset className="grid gap-3">
            <legend className="mb-1 text-sm font-medium">How often should your agent plan posts?</legend>
            <div className="flex items-center gap-4">
              <input type="range" min={1} max={14} value={p.posts_per_week} onChange={(e) => set("posts_per_week", Number(e.target.value))} className="w-56 accent-[var(--lab)]" aria-label="Posts per week" />
              <span className="numeric font-medium">{p.posts_per_week} {p.posts_per_week === 1 ? "post" : "posts"} a week</span>
            </div>
            <p className="text-sm text-muted">Three to five a week is a sustainable start for most small businesses.</p>
          </fieldset>
          <fieldset className="grid gap-3">
            <legend className="mb-1 text-sm font-medium">Approval</legend>
            <label className="flex items-start gap-3 text-sm">
              <input type="checkbox" className="mt-1 size-4 accent-[var(--lab)]" checked={p.approval_required} disabled={!business.can_auto_publish && p.approval_required} onChange={(e) => set("approval_required", e.target.checked)} />
              <span>
                <span className="block font-medium">Ask me to approve every post before it&apos;s published</span>
                <span className="block text-muted">
                  {business.can_auto_publish ? "Turn this off to let posts publish at their scheduled time without waiting for you. They're still checked first." : "Publishing without approval is available on the Business and Agency plans."}
                </span>
              </span>
            </label>
          </fieldset>
          <fieldset className="grid gap-3">
            <legend className="mb-1 text-sm font-medium">Remind me about posts waiting for approval</legend>
            <div className="flex flex-wrap gap-2">
              {REMINDERS.map((r) => (
                <Toggle key={r.hours} pressed={p.reminder_offsets_hours.includes(r.hours)} onClick={() => set("reminder_offsets_hours", toggle(p.reminder_offsets_hours, r.hours))} className="rounded-full px-4 py-1.5">{r.label}</Toggle>
              ))}
            </div>
            {!p.reminder_offsets_hours.length && <p className="text-sm text-muted">No reminders. Posts you haven&apos;t approved won&apos;t publish.</p>}
          </fieldset>
        </>
      )}
      <FormActions>
        <Button type="submit" loading={save.isPending}>{submitLabel}</Button>
        {secondary}
      </FormActions>
    </form>
  );
}
