"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, Circle, CircleDashed } from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { businessApi, mediaApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";
import type { Business } from "@/types/api";
import { BrandForm } from "../business/brand-form";
import { GOALS, PLATFORMS } from "../business/options";
import { PreferencesForm } from "../business/preferences-form";
import { ProductsEditor } from "../business/products-editor";
import { AudienceForm, ProfileForm } from "../business/profile-form";
import { useBusiness } from "../business/use-business";
import { useSession } from "../session";
import { MediaStep } from "./media-step";

const STEPS = [
  { title: "Your business", lead: "The basics your agent needs to write about you accurately." },
  { title: "Customers and goals", lead: "Who you're talking to, and what marketing should achieve." },
  { title: "Brand voice", lead: "How your posts should sound, and what they must never say." },
  { title: "Products and services", lead: "What you sell. Your agent features these in posts and promotions." },
  { title: "Photos and videos", lead: "Real photos build trust. Your agent uses these before generating anything." },
  { title: "Publishing", lead: "Where, how often, and how much control you want." },
  { title: "Review", lead: "Here's what your agent knows. You can change any of it later in Settings." },
] as const;

function Summary({ business }: { business: Business }) {
  const { workspace } = useSession();
  const media = useQuery({ queryKey: ["media", workspace.id, { count: true }], queryFn: () => mediaApi.list(workspace.id, { limit: 1 }) });
  const p = business.profile;
  const rows: { label: string; value: string | null }[] = [
    { label: "Business", value: p ? [p.name, p.industry, p.location].filter(Boolean).join(", ") : null },
    { label: "Goals", value: p?.marketing_goals.length ? p.marketing_goals.map((g) => GOALS.find((x) => x.id === g)?.label ?? g).join(", ") : null },
    { label: "Customers", value: p?.audience.description || (p?.audience.customer_types.length ? p.audience.customer_types.join(", ") : null) },
    { label: "Voice", value: business.brand.tone.length ? business.brand.tone.join(", ") : business.brand.voice },
    { label: "Topics to avoid", value: p?.topics_to_avoid.length ? p.topics_to_avoid.join(", ") : null },
    { label: "Products", value: business.products.length ? business.products.map((x) => x.name).join(", ") : null },
    { label: "Photos and videos", value: media.data ? (media.data.total ? `${media.data.total} in your library` : null) : "…" },
    { label: "Platforms", value: business.preferences.preferred_platforms.length ? business.preferences.preferred_platforms.map((id) => PLATFORMS.find((x) => x.id === id)?.label ?? id).join(", ") : null },
    { label: "Rhythm", value: `${business.preferences.posts_per_week} posts a week, ${business.preferences.approval_required ? "approval required" : "publishes without approval"}` },
  ];
  return (
    <dl className="divide-y divide-line border-y border-line">
      {rows.map((r) => (
        <div key={r.label} className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
          <dt className="text-sm text-muted">{r.label}</dt>
          <dd className={cn("text-sm", !r.value && "text-faint")}>{r.value ?? "Not added yet"}</dd>
        </div>
      ))}
    </dl>
  );
}

export function OnboardingWizard() {
  const router = useRouter();
  const { workspace } = useSession();
  const biz = useBusiness();
  const [step, setStep] = useState<number | null>(null);


  const progress = useMutation({ mutationFn: (s: number) => businessApi.setOnboarding(workspace.id, s) });
  const finish = useMutation({
    mutationFn: () => businessApi.setOnboarding(workspace.id, 7, true),
    onSuccess: () => {
      biz.refresh();
      router.push("/dashboard");
    },
  });

  const go = (next: number) => {
    setStep(next);
    progress.mutate(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (!biz.canManage) {
    return (
      <main id="main" className="mx-auto grid max-w-lg gap-4 px-6 py-24">
        <Logo href="/dashboard" />
        <Alert tone="info" title="Setup is done by the workspace owner">Ask an owner or admin of {workspace.name} to finish setting up the business.</Alert>
        <Button asChild variant="secondary"><Link href="/dashboard">Go to dashboard</Link></Button>
      </main>
    );
  }

  // Resume where the user left off until they navigate.
  const saved = biz.data ? (biz.data.onboarding.completed ? 7 : biz.data.onboarding.step) : 1;
  const current = step ?? saved;
  const meta = STEPS[current - 1]!;
  const back = current > 1 ? <Button type="button" variant="ghost" onClick={() => go(current - 1)}>Back</Button> : null;
  const skip = (
    <>
      {back}
      {current > 1 && current < 7 && (
        <button type="button" onClick={() => go(current + 1)} className="ml-auto text-sm text-muted hover:text-ink">Skip for now</button>
      )}
    </>
  );
  const next = () => go(current + 1);
  const fallbackName = workspace.name;

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[20rem_1fr]">
      <aside className="border-b border-line bg-paper px-6 py-5 lg:sticky lg:top-0 lg:h-dvh lg:border-b-0 lg:border-r lg:px-8 lg:py-8">
        <div className="flex items-center justify-between lg:block">
          <Logo href="/dashboard" />
          <p className="numeric text-sm text-muted lg:hidden">Step {current} of 7</p>
        </div>
        <ol className="mt-10 hidden gap-1 lg:grid" aria-label="Setup steps">
          {STEPS.map((s, i) => {
            const n = i + 1;
            const done = n < current || biz.data?.onboarding.completed;
            const Icon = done ? Check : n === current ? Circle : CircleDashed;
            return (
              <li key={s.title}>
                <button
                  type="button"
                  onClick={() => n <= Math.max(current, biz.data?.onboarding.step ?? 1) && go(n)}
                  aria-current={n === current ? "step" : undefined}
                  className={cn("flex w-full items-center gap-3 rounded-[var(--radius-control)] px-3 py-2 text-left text-sm text-muted", n === current && "bg-surface font-medium text-ink ring-1 ring-line")}
                >
                  <Icon className={cn("size-4", done && "text-lab", n === current && "text-lab")} aria-hidden />
                  {s.title}
                </button>
              </li>
            );
          })}
        </ol>
        <div className="mt-4 h-1 overflow-hidden rounded-full bg-sunk lg:hidden" aria-hidden>
          <div className="h-full bg-lab transition-[width]" style={{ width: `${(current / 7) * 100}%` }} />
        </div>
        <Link href="/dashboard" className="mt-10 hidden text-sm text-muted hover:text-ink lg:inline-block">Finish later</Link>
      </aside>

      <main id="main" className="px-6 py-10 sm:px-10 lg:px-16 lg:py-16">
        <div className="mx-auto grid max-w-2xl gap-8">
          <header className="grid gap-2">
            <p className="numeric hidden text-sm text-muted lg:block">Step {current} of 7</p>
            <h1 className="display text-4xl sm:text-5xl">{meta.title}</h1>
            <p className="text-lg text-muted">{meta.lead}</p>
          </header>

          {!biz.data ? (
            <div className="grid gap-4" aria-busy="true"><Skeleton className="h-11" /><Skeleton className="h-11" /><Skeleton className="h-32" /></div>
          ) : (
            <div key={current}>
              {current === 1 && <ProfileForm business={biz.data} fallbackName={fallbackName} submitLabel="Continue" onSaved={next} />}
              {current === 2 && <AudienceForm business={biz.data} fallbackName={fallbackName} submitLabel="Continue" onSaved={next} secondary={skip} />}
              {current === 3 && <BrandForm business={biz.data} fallbackName={fallbackName} submitLabel="Continue" onSaved={next} secondary={skip} />}
              {current === 4 && (
                <div className="grid gap-6">
                  <ProductsEditor products={biz.data.products} />
                  <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
                    <Button type="button" onClick={next}>Continue</Button>
                    {back}
                  </div>
                </div>
              )}
              {current === 5 && <MediaStep business={biz.data} workspaceId={workspace.id} onSaved={next} secondary={skip} />}
              {current === 6 && <PreferencesForm business={biz.data} only="publishing" submitLabel="Continue" onSaved={next} secondary={skip} />}
              {current === 7 && (
                <div className="grid gap-8">
                  <Summary business={biz.data} />
                  <section className="grid gap-3 rounded-[var(--radius-card)] bg-surface p-5 ring-1 ring-line">
                    <h2 className="font-semibold">What happens next</h2>
                    <ul className="grid gap-2 text-sm text-muted">
                      <li className="flex gap-2"><Check className="mt-0.5 size-4 shrink-0 text-lab" aria-hidden /> Your business profile, brand and media are saved and ready for your agent.</li>
                      <li className="flex gap-2"><CircleDashed className="mt-0.5 size-4 shrink-0" aria-hidden /> Connecting social accounts and AI-drafted posts are being built. Your dashboard will tell you when each is available.</li>
                    </ul>
                  </section>
                  {finish.error && <Alert tone="error" title="Couldn't finish setup">Try again.</Alert>}
                  <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
                    <Button onClick={() => finish.mutate()} loading={finish.isPending}>{biz.data.onboarding.completed ? "Back to dashboard" : "Finish setup"}</Button>
                    {back}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
