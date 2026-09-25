"use client";

import { useState } from "react";
import { useTheme } from "next-themes";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, CreditCard, ExternalLink, Loader2 } from "lucide-react";
import { useSession } from "@/components/app/session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Meter } from "@/components/ui/meter";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { billingApi, contentApi } from "@/lib/api/endpoints";
import { openCheckout } from "@/lib/paddle";
import { PLANS, type PlanId } from "@/lib/plans";
import { cn } from "@/lib/utils";
import type { Billing } from "@/types/api";
import { SettingsSection } from "./section";

const ORDER: PlanId[] = ["free", "starter", "business", "agency"];
const STATUS: Record<Billing["status"], { label: string; tone: string }> = {
  active: { label: "Active", tone: "bg-lab-soft text-lab" },
  trialing: { label: "Trial", tone: "bg-lab-soft text-lab" },
  past_due: { label: "Payment problem", tone: "bg-signal-soft text-signal" },
  paused: { label: "Paused", tone: "bg-sunk text-muted" },
  canceled: { label: "Canceled", tone: "bg-sunk text-muted" },
};

const keyOf = (b?: Billing) => (b ? `${b.plan}|${b.status}|${b.scheduled_change?.action ?? ""}|${b.last_webhook_at ?? ""}` : "");
const fmtDate = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }) : "");
const errText = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Try again.");

export function BillingSettings() {
  const { workspace } = useSession();
  const { resolvedTheme } = useTheme();
  // After checkout or a plan change we wait for Paddle's webhook, the only source of truth.
  const [waiting, setWaiting] = useState<{ from: string } | null>(null);
  const [slow, setSlow] = useState(false);
  const [confirm, setConfirm] = useState<PlanId | "cancel" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const billing = useQuery({
    queryKey: ["billing"],
    queryFn: billingApi.get,
    // Poll only until the webhook-driven state changes.
    refetchInterval: (q) => (waiting && keyOf(q.state.data) === waiting.from ? 2000 : false),
  });
  const b = billing.data;
  const confirmedKey = keyOf(b);
  const isWaiting = !!waiting && confirmedKey === waiting.from;
  // Keyed on the billing state, so limits refresh by themselves once a change is confirmed.
  const usage = useQuery({ queryKey: ["usage", workspace.id, confirmedKey], queryFn: () => contentApi.usage(workspace.id) });
  const waitedTooLong = isWaiting && slow;

  const startWaiting = () => {
    setWaiting({ from: confirmedKey });
    setSlow(false);
    window.setTimeout(() => setSlow(true), 60_000);
  };

  const checkout = useMutation({
    mutationFn: async (plan: PlanId) => {
      const params = await billingApi.checkout(plan);
      await openCheckout(params, (name) => name === "checkout.completed" && startWaiting(), resolvedTheme === "dark" ? "dark" : "light");
    },
    onError: (e) => setError(errText(e)),
  });
  const change = useMutation({
    mutationFn: (plan: PlanId) => billingApi.changePlan(plan),
    onSuccess: () => { setConfirm(null); startWaiting(); },
    onError: (e) => { setConfirm(null); setError(errText(e)); },
  });
  const cancel = useMutation({ mutationFn: billingApi.cancel, onSuccess: () => { setConfirm(null); startWaiting(); }, onError: (e) => { setConfirm(null); setError(errText(e)); } });
  const resume = useMutation({ mutationFn: billingApi.resume, onSuccess: startWaiting, onError: (e) => setError(errText(e)) });
  const portal = useMutation({
    mutationFn: billingApi.portal,
    onSuccess: ({ url }) => window.open(url, "_blank", "noopener,noreferrer"),
    onError: (e) => setError(errText(e)),
  });

  if (billing.isPending) return <div className="grid gap-4"><Skeleton className="h-32" /><Skeleton className="h-64" /></div>;
  if (!b) return <Alert tone="error" title="Billing didn't load">{errText(billing.error)}</Alert>;

  const current = PLANS.find((p) => p.id === b.plan)!;
  const status = STATUS[b.status];
  const canceling = b.scheduled_change?.action === "cancel";
  const u = usage.data;

  return (
    <div className="grid gap-10">
      {error && <Alert tone="error" title="That didn't work">{error} <button className="underline" onClick={() => setError(null)}>Dismiss</button></Alert>}
      {isWaiting && (
        <Alert tone="info" title={waitedTooLong ? "Still waiting for Paddle" : "Confirming with Paddle"}>
          <span className="inline-flex items-center gap-2">
            {!waitedTooLong && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
            {waitedTooLong
              ? "Your change was sent, but Paddle hasn't confirmed it yet. This page updates as soon as it does; you won't be charged twice."
              : "Your plan updates as soon as Paddle confirms. This usually takes a few seconds."}
          </span>
        </Alert>
      )}
      {!b.configured && (
        <Alert tone="info" title="Paid plans aren't available on this server">
          Billing isn&apos;t configured (the PADDLE_* settings are missing), so plans can&apos;t be bought here. Everything else works on your current plan.
        </Alert>
      )}
      {b.status === "past_due" && (
        <Alert tone="error" title="Your last payment didn't go through">
          Paddle will retry automatically. Update your payment method to keep {current.name} features.
        </Alert>
      )}

      <SettingsSection title="Your plan" description="Billing is per account and covers every business you own.">
        <div className="grid gap-4 rounded-[var(--radius-card)] bg-surface p-5 ring-1 ring-line">
          <div className="flex flex-wrap items-baseline gap-3">
            <p className="display text-3xl">{current.name}</p>
            <p className="numeric text-muted">
              {b.price_cents != null && b.has_paddle_subscription ? `${(b.price_cents / 100).toFixed(2)} ${b.currency} / month` : `$${current.priceUsd} / month`}
            </p>
            <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", status.tone)}>{status.label}</span>
          </div>
          {b.manual_override && <p className="text-sm text-muted">This plan was set by ContentFactory support.</p>}
          {b.has_paddle_subscription && b.current_period_end && (
            <p className="text-sm text-muted">{canceling ? `Ends on ${fmtDate(b.scheduled_change?.effective_at ?? b.current_period_end)}. After that you move to Free; your content stays.` : `Renews on ${fmtDate(b.current_period_end)}.`}</p>
          )}
          {b.has_paddle_subscription && (
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" onClick={() => portal.mutate()} loading={portal.isPending}><CreditCard /> Invoices and payment method <ExternalLink className="size-3.5" /></Button>
              {canceling ? (
                <Button size="sm" onClick={() => resume.mutate()} loading={resume.isPending}>Keep my subscription</Button>
              ) : (
                <Button variant="ghost" size="sm" onClick={() => setConfirm("cancel")}>Cancel subscription</Button>
              )}
            </div>
          )}
        </div>
      </SettingsSection>

      <SettingsSection title="Usage this period" description={u ? `${fmtDate(u.period_start)} to ${fmtDate(u.period_end)}, for ${workspace.name}.` : undefined}>
        {u ? (
          <div className="grid gap-5">
            <Meter label="AI drafts" used={u.ai_content.used} limit={u.ai_content.limit} />
            <Meter label="Image generations" used={u.images.used} limit={u.images.limit} />
            <Meter label="AI video credits" used={u.video_credits.used} limit={u.video_credits.limit} />
            <Meter label="Scheduled posts this month" used={u.scheduled_posts.used} limit={u.scheduled_posts.limit} />
            <p className="text-xs text-muted">Failed AI work is never counted, and repeating an identical request is free.</p>
          </div>
        ) : (
          <Skeleton className="h-40" />
        )}
      </SettingsSection>

      <section className="grid gap-4">
        <h2 className="text-lg font-semibold">Plans</h2>
        <div className="grid gap-px overflow-hidden rounded-[var(--radius-card)] bg-line ring-1 ring-line md:grid-cols-2 xl:grid-cols-4">
          {PLANS.map((p) => {
            const isCurrent = p.id === b.plan;
            const higher = ORDER.indexOf(p.id) > ORDER.indexOf(b.plan);
            let action: React.ReactNode = null;
            if (isCurrent) action = <span className="inline-flex h-9 items-center gap-1.5 text-sm font-medium text-lab"><Check className="size-4" /> Current plan</span>;
            else if (p.id === "free") action = b.has_paddle_subscription && !canceling ? <Button variant="ghost" size="sm" onClick={() => setConfirm("cancel")}>Move to Free</Button> : null;
            else if (b.has_paddle_subscription) action = <Button variant={higher ? "primary" : "secondary"} size="sm" disabled={!b.configured || isWaiting} onClick={() => setConfirm(p.id)}>{higher ? "Upgrade" : "Downgrade"} to {p.name}</Button>;
            else action = <Button variant={p.recommended ? "primary" : "secondary"} size="sm" disabled={!b.configured || isWaiting || !!b.manual_override} onClick={() => checkout.mutate(p.id)} loading={checkout.isPending && checkout.variables === p.id}>Choose {p.name}</Button>;
            return (
              <div key={p.id} className={cn("grid content-start gap-3 bg-surface p-5", isCurrent && "bg-lab-soft/50")}>
                <div className="flex items-baseline justify-between">
                  <h3 className="font-semibold">{p.name}</h3>
                  <p className="numeric text-sm text-muted">${p.priceUsd}/mo</p>
                </div>
                <ul className="grid gap-1 text-sm text-muted">
                  <li>{p.aiContent} AI drafts, {p.images} images</li>
                  <li>{p.videoCredits} video credits, {p.scheduledPosts.toLocaleString("en-US")} scheduled posts</li>
                  <li>{p.businesses} {p.businesses === 1 ? "business" : "businesses"}, {p.socialAccounts} social accounts</li>
                  <li>{p.autoPublish ? "Approval optional" : "Every post needs approval"}</li>
                </ul>
                <div>{action}</div>
              </div>
            );
          })}
        </div>
        <p className="text-sm text-muted">Payments are handled by Paddle, our merchant of record. Sales tax or VAT is added where it applies.</p>
      </section>

      <Dialog open={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)}>
        {confirm === "cancel" && (
          <DialogContent title="Cancel your subscription?" description={`You keep ${current.name} until ${fmtDate(b.current_period_end)}. Then you move to Free: your content, media and memory stay, and features above Free are turned off.`}>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setConfirm(null)}>Keep subscription</Button>
              <Button variant="danger" onClick={() => cancel.mutate()} loading={cancel.isPending}>Cancel at period end</Button>
            </div>
          </DialogContent>
        )}
        {confirm && confirm !== "cancel" && (() => {
          const target = PLANS.find((p) => p.id === confirm)!;
          const up = ORDER.indexOf(confirm) > ORDER.indexOf(b.plan);
          return (
            <DialogContent
              title={`${up ? "Upgrade" : "Downgrade"} to ${target.name}?`}
              description={up
                ? `You're charged the prorated difference now, and ${target.name} limits apply as soon as Paddle confirms.`
                : `The unused part of this period is credited to your next bill. Features ${target.name} doesn't include (like publishing without approval) are turned off; nothing is deleted.`}
            >
              <div className="mt-5 flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setConfirm(null)}>Not now</Button>
                <Button onClick={() => change.mutate(confirm)} loading={change.isPending}>{up ? "Upgrade" : "Downgrade"}</Button>
              </div>
            </DialogContent>
          );
        })()}
      </Dialog>
    </div>
  );
}
