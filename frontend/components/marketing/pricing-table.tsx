import Link from "next/link";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PLANS } from "@/lib/plans";
import { cn } from "@/lib/utils";

function limitRows(p: (typeof PLANS)[number]) {
  return [
    `${p.businesses} ${p.businesses === 1 ? "business" : "businesses"}`,
    `${p.socialAccounts} social ${p.socialAccounts === 1 ? "account" : "accounts"}`,
    `${p.aiContent} AI content generations / month`,
    `${p.images} image generations / month`,
    `${p.videoCredits} AI video credits / month`,
    `${p.scheduledPosts.toLocaleString("en-US")} scheduled posts`,
  ];
}

export function PricingTable({ compact = false }: { compact?: boolean }) {
  return (
    <div className="grid gap-px overflow-hidden rounded-[var(--radius-frame)] bg-line ring-1 ring-line md:grid-cols-2 xl:grid-cols-4">
      {PLANS.map((plan) => (
        <div
          key={plan.id}
          className={cn("relative grid content-start gap-6 bg-surface p-6", plan.recommended && "bg-lab-soft/50 dark:bg-lab-soft/40")}
        >
          <div className="grid gap-1">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-lg font-semibold">{plan.name}</h3>
              {plan.recommended && (
                <span className="rounded-full bg-lab px-2.5 py-0.5 text-xs font-medium text-on-lab">Recommended</span>
              )}
            </div>
            <p className="text-sm text-muted">{plan.tagline}</p>
          </div>
          <p className="flex items-baseline gap-1.5">
            <span className="display numeric text-4xl">${plan.priceUsd}</span>
            <span className="text-sm text-muted">/ month</span>
          </p>
          <Button asChild variant={plan.recommended ? "primary" : "secondary"}>
            <Link href={`/register?plan=${plan.id}`}>{plan.priceUsd === 0 ? "Start free" : `Choose ${plan.name}`}</Link>
          </Button>
          <ul className="grid gap-2 text-sm">
            {limitRows(plan).map((row) => (
              <li key={row} className="numeric">{row}</li>
            ))}
          </ul>
          {!compact && (
            <ul className="grid gap-2 border-t border-line pt-5 text-sm">
              {plan.features.map((f) => (
                <li key={f} className="flex gap-2">
                  <Check className="mt-0.5 size-4 shrink-0 text-lab" aria-hidden />
                  <span>{f}</span>
                </li>
              ))}
              {!plan.autoPublish && (
                <li className="pl-6 text-muted">Every post needs your approval.</li>
              )}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
