"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ChipsInput } from "@/components/ui/chips-input";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { businessApi } from "@/lib/api/endpoints";
import type { Business, BusinessProfile } from "@/types/api";
import { FormActions, FormError, Toggle, toggle } from "./form-bits";
import { GOALS, LANGUAGES } from "./options";
import { emptyProfile, useBusiness } from "./use-business";

interface FormProps {
  business: Business;
  submitLabel: string;
  onSaved?: () => void;
  secondary?: React.ReactNode;
}

function useProfileSave(onSaved?: () => void) {
  const { workspaceId, update, refresh } = useBusiness();
  return useMutation({
    mutationFn: (p: BusinessProfile) => businessApi.saveProfile(workspaceId, p),
    onSuccess: (profile) => {
      update((b) => ({ ...b, profile }));
      refresh();
      onSaved?.();
    },
  });
}

/** Step 1: who you are. */
export function ProfileForm({ business, submitLabel, onSaved, secondary, fallbackName }: FormProps & { fallbackName: string }) {
  const [p, setP] = useState<BusinessProfile>(business.profile ?? emptyProfile(fallbackName));
  const save = useProfileSave(onSaved);
  const set = <K extends keyof BusinessProfile>(k: K, v: BusinessProfile[K]) => setP((x) => ({ ...x, [k]: v }));

  return (
    <form className="grid gap-5" onSubmit={(e) => { e.preventDefault(); save.mutate(p); }}>
      <FormError error={save.error} />
      <Field id="biz-name" label="Business name">
        <Input value={p.name} onChange={(e) => set("name", e.target.value)} required maxLength={120} autoComplete="organization" />
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="biz-industry" label="What kind of business?" hint="For example: café, hair salon, bike shop">
          <Input value={p.industry ?? ""} onChange={(e) => set("industry", e.target.value)} maxLength={120} />
        </Field>
        <Field id="biz-location" label="Where are you?" hint="City, neighbourhood, or 'online only'">
          <Input value={p.location ?? ""} onChange={(e) => set("location", e.target.value)} maxLength={200} />
        </Field>
      </div>
      <div className="grid gap-5 sm:grid-cols-[1fr_12rem]">
        <Field id="biz-website" label="Website" hint="Optional">
          <Input value={p.website ?? ""} onChange={(e) => set("website", e.target.value)} inputMode="url" placeholder="example.com" />
        </Field>
        <Field id="biz-language" label="Post language">
          <Select value={p.preferred_language} onChange={(e) => set("preferred_language", e.target.value)}>
            {LANGUAGES.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
          </Select>
        </Field>
      </div>
      <Field id="biz-description" label="Describe your business in a few sentences" hint="What you offer, what makes it special, what customers love.">
        <Textarea value={p.description ?? ""} onChange={(e) => set("description", e.target.value)} maxLength={4000} rows={4} />
      </Field>
      <FormActions>
        <Button type="submit" loading={save.isPending}>{submitLabel}</Button>
        {secondary}
      </FormActions>
    </form>
  );
}

/** Step 2: customers and goals (same profile record). */
export function AudienceForm({ business, submitLabel, onSaved, secondary, fallbackName }: FormProps & { fallbackName: string }) {
  const [p, setP] = useState<BusinessProfile>(business.profile ?? emptyProfile(fallbackName));
  const save = useProfileSave(onSaved);
  const setAudience = (k: keyof BusinessProfile["audience"], v: string | string[] | null) => setP((x) => ({ ...x, audience: { ...x.audience, [k]: v } }));

  return (
    <form className="grid gap-6" onSubmit={(e) => { e.preventDefault(); save.mutate(p); }}>
      <FormError error={save.error} />
      <fieldset className="grid gap-3">
        <legend className="mb-1 text-sm font-medium">What should marketing do for you? <span className="font-normal text-muted">Pick up to three.</span></legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {GOALS.map((g) => {
            const on = p.marketing_goals.includes(g.id);
            return (
              <Toggle key={g.id} pressed={on} disabled={!on && p.marketing_goals.length >= 3} onClick={() => setP((x) => ({ ...x, marketing_goals: toggle(x.marketing_goals, g.id) }))}>
                <span className="block font-medium">{g.label}</span>
                <span className="block text-xs text-muted">{g.hint}</span>
              </Toggle>
            );
          })}
        </div>
      </fieldset>
      <Field id="aud-description" label="Who are your best customers?" hint="Age, lifestyle, why they come to you.">
        <Textarea value={p.audience.description ?? ""} onChange={(e) => setAudience("description", e.target.value)} maxLength={2000} rows={3} className="min-h-24" />
      </Field>
      <Field id="aud-types" label="Customer groups" hint="Press Enter after each, e.g. students, young parents, office workers">
        <ChipsInput value={p.audience.customer_types} onChange={(v) => setAudience("customer_types", v)} />
      </Field>
      <Field id="aud-pain" label="What problems do you solve for them?" hint="Optional">
        <ChipsInput value={p.audience.pain_points} onChange={(v) => setAudience("pain_points", v)} />
      </Field>
      <Field id="aud-usp" label="Why choose you over others?" hint="Your strengths, in a few words each">
        <ChipsInput value={p.unique_selling_points} onChange={(v) => setP((x) => ({ ...x, unique_selling_points: v }))} placeholder="Roasted in-house, open until midnight" />
      </Field>
      <FormActions>
        <Button type="submit" loading={save.isPending}>{submitLabel}</Button>
        {secondary}
      </FormActions>
    </form>
  );
}
