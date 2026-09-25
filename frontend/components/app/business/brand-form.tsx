"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ImageIcon, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChipsInput } from "@/components/ui/chips-input";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/input";
import { businessApi } from "@/lib/api/endpoints";
import type { BrandSettings, Business, BusinessProfile } from "@/types/api";
import { FormActions, FormError, Toggle, toggle } from "./form-bits";
import { MediaPicker } from "./media-picker";
import { TONES } from "./options";
import { emptyProfile, useBusiness } from "./use-business";

export function BrandForm({ business, submitLabel, onSaved, secondary, fallbackName }: {
  business: Business;
  submitLabel: string;
  onSaved?: () => void;
  secondary?: React.ReactNode;
  fallbackName: string;
}) {
  const { workspaceId, update, refresh } = useBusiness();
  const [brand, setBrand] = useState<BrandSettings>(business.brand);
  const [avoid, setAvoid] = useState<string[]>(business.profile?.topics_to_avoid ?? []);
  const [pickLogo, setPickLogo] = useState(false);
  const [logoPreview, setLogoPreview] = useState<string | null>(business.brand.logo_url ?? null);
  const set = <K extends keyof BrandSettings>(k: K, v: BrandSettings[K]) => setBrand((b) => ({ ...b, [k]: v }));

  const save = useMutation({
    mutationFn: async () => {
      const saved = await businessApi.saveBrand(workspaceId, {
        voice: brand.voice,
        tone: brand.tone,
        colors: brand.colors,
        visual_style: brand.visual_style,
        words_to_use: brand.words_to_use,
        words_to_avoid: brand.words_to_avoid,
        logo_asset_id: brand.logo_asset_id,
      });
      // Forbidden topics live on the profile; save them together so the step is one action.
      const profile: BusinessProfile = { ...(business.profile ?? emptyProfile(fallbackName)), topics_to_avoid: avoid };
      const savedProfile = await businessApi.saveProfile(workspaceId, profile);
      return { saved, savedProfile };
    },
    onSuccess: ({ saved, savedProfile }) => {
      update((b) => ({ ...b, brand: saved, profile: savedProfile }));
      refresh();
      onSaved?.();
    },
  });

  return (
    <form className="grid gap-6" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <FormError error={save.error} />
      <fieldset className="grid gap-3">
        <legend className="mb-1 text-sm font-medium">How should your posts sound? <span className="font-normal text-muted">Pick a few.</span></legend>
        <div className="flex flex-wrap gap-2">
          {TONES.map((t) => {
            const on = brand.tone.includes(t);
            return <Toggle key={t} pressed={on} disabled={!on && brand.tone.length >= 5} onClick={() => set("tone", toggle(brand.tone, t))} className="rounded-full px-4 py-1.5">{t}</Toggle>;
          })}
        </div>
      </fieldset>
      <Field id="brand-voice" label="Describe your voice in your own words" hint="How would you talk to a regular customer at the counter?">
        <Textarea value={brand.voice ?? ""} onChange={(e) => set("voice", e.target.value)} maxLength={2000} rows={3} className="min-h-24" placeholder="Warm and direct. We explain coffee without being snobby about it." />
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="brand-use" label="Words and phrases to use">
          <ChipsInput value={brand.words_to_use} onChange={(v) => set("words_to_use", v)} />
        </Field>
        <Field id="brand-avoid" label="Words to never use">
          <ChipsInput value={brand.words_to_avoid} onChange={(v) => set("words_to_avoid", v)} />
        </Field>
      </div>
      <Field id="brand-topics" label="Topics your posts must avoid" hint="Your agent is told never to write about these, and drafts that mention them are flagged.">
        <ChipsInput value={avoid} onChange={setAvoid} placeholder="Politics, competitors by name" />
      </Field>

      <fieldset className="grid gap-3">
        <legend className="mb-1 text-sm font-medium">Brand colours <span className="font-normal text-muted">Optional, up to 6</span></legend>
        <div className="flex flex-wrap items-center gap-3">
          {brand.colors.map((c, i) => (
            <span key={`${c}-${i}`} className="inline-flex items-center gap-2 rounded-full bg-sunk py-1 pl-1 pr-2 text-sm">
              <label className="relative size-7 overflow-hidden rounded-full ring-1 ring-line-strong" style={{ background: c }}>
                <span className="sr-only">Colour {i + 1}</span>
                <input type="color" value={c.toLowerCase()} onChange={(e) => set("colors", brand.colors.map((x, j) => (j === i ? e.target.value.toUpperCase() : x)))} className="absolute inset-0 cursor-pointer opacity-0" />
              </label>
              <span className="numeric">{c}</span>
              <button type="button" onClick={() => set("colors", brand.colors.filter((_, j) => j !== i))} aria-label={`Remove ${c}`} className="text-muted hover:text-ink"><X className="size-3.5" /></button>
            </span>
          ))}
          {brand.colors.length < 6 && (
            <Button type="button" variant="secondary" size="sm" onClick={() => set("colors", [...brand.colors, "#0E6B63"])}><Plus /> Add colour</Button>
          )}
        </div>
      </fieldset>

      <div className="grid gap-2">
        <p className="text-sm font-medium">Logo <span className="font-normal text-muted">Optional</span></p>
        <div className="flex items-center gap-3">
          <div className="grid size-16 place-items-center overflow-hidden rounded-[var(--radius-control)] bg-sunk ring-1 ring-line">
            {/* eslint-disable-next-line @next/next/no-img-element -- signed storage URL */}
            {logoPreview ? <img src={logoPreview} alt="Logo" className="size-full object-contain" /> : <ImageIcon className="size-5 text-faint" aria-hidden />}
          </div>
          <Button type="button" variant="secondary" size="sm" onClick={() => setPickLogo(true)}>{brand.logo_asset_id ? "Change" : "Choose from library"}</Button>
          {brand.logo_asset_id && <Button type="button" variant="ghost" size="sm" onClick={() => { set("logo_asset_id", null); setLogoPreview(null); }}>Remove</Button>}
        </div>
      </div>
      <MediaPicker
        workspaceId={workspaceId}
        open={pickLogo}
        onOpenChange={setPickLogo}
        max={1}
        title="Choose your logo"
        selected={brand.logo_asset_id ? [brand.logo_asset_id] : []}
        onConfirm={(ids, assets) => { set("logo_asset_id", ids[0] ?? null); setLogoPreview(assets[0]?.thumbnail_url ?? assets[0]?.url ?? null); }}
      />
      <FormActions>
        <Button type="submit" loading={save.isPending}>{submitLabel}</Button>
        {secondary}
      </FormActions>
    </form>
  );
}
