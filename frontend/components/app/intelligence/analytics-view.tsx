"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { PageTitle } from "@/components/app/page-title";
import { useSession } from "@/components/app/session";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { intelligenceApi } from "@/lib/api/endpoints";
import { cn, formatNumber } from "@/lib/utils";
import type { Analytics } from "@/types/api";
import { PILLAR_LABELS, PLATFORM_RULES } from "../content/meta";

const KPIS: { key: keyof Analytics["totals"]; label: string }[] = [
  { key: "reach", label: "Reach" },
  { key: "views", label: "Views" },
  { key: "engagements", label: "Engagements" },
  { key: "saves", label: "Saves" },
  { key: "shares", label: "Shares" },
  { key: "comments", label: "Comments" },
];

const fmt = (v: number | null) => (v === null ? null : formatNumber(Math.round(v)));

function Chart({ daily }: { daily: Analytics["daily"] }) {
  const max = Math.max(1, ...daily.map((d) => d.engagements));
  const w = 100 / daily.length;
  return (
    <figure className="grid gap-2">
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="h-40 w-full" role="img" aria-label="Engagements per day">
        {daily.map((d, i) => {
          const h = (d.engagements / max) * 36;
          return (
            <g key={d.date}>
              <rect x={i * w + w * 0.15} y={38 - h} width={w * 0.7} height={Math.max(h, d.posts ? 0.6 : 0)} rx={0.4} className="fill-lab" />
              {d.posts > 0 && <circle cx={i * w + w / 2} cy={39.4} r={0.5} className="fill-marker" />}
              <title>{`${d.date}: ${Math.round(d.engagements)} engagements, ${d.posts} post${d.posts === 1 ? "" : "s"}`}</title>
            </g>
          );
        })}
      </svg>
      <figcaption className="flex justify-between text-xs text-muted">
        <span>{daily[0]?.date}</span>
        <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-marker" aria-hidden /> day with a post</span>
        <span>{daily[daily.length - 1]?.date}</span>
      </figcaption>
    </figure>
  );
}

export function AnalyticsView() {
  const { workspace } = useSession();
  const [days, setDays] = useState(30);
  const q = useQuery({ queryKey: ["analytics", workspace.id, days], queryFn: () => intelligenceApi.analytics(workspace.id, days) });
  const a = q.data;

  return (
    <div className="mx-auto grid max-w-6xl gap-8">
      <PageTitle
        title="Analytics"
        description="Performance of published posts, as reported by each platform. Metrics a platform doesn't provide are shown as not available, never as zero."
        actions={
          <div role="radiogroup" aria-label="Period" className="inline-flex rounded-[var(--radius-control)] bg-sunk p-1 text-sm">
            {[7, 30, 90].map((d) => (
              <button key={d} role="radio" aria-checked={days === d} onClick={() => setDays(d)} className={cn("rounded-[7px] px-3 py-1.5 text-muted", days === d && "bg-surface font-medium text-ink shadow-sm")}>{d} days</button>
            ))}
          </div>
        }
      />
      {q.isPending ? (
        <Skeleton className="h-80" />
      ) : !a ? (
        <Alert tone="error" title="Analytics didn't load">Try again.</Alert>
      ) : a.posts_published === 0 ? (
        <div className="grid justify-items-start gap-3 rounded-[var(--radius-card)] border border-dashed border-line-strong bg-surface/60 px-6 py-12">
          <h2 className="text-lg font-semibold">Nothing published in the last {days} days</h2>
          <p className="max-w-lg text-muted">Numbers appear here after posts go out through a connected account. Metrics are collected over each post&apos;s first month.</p>
          <Link href="/calendar" className="text-sm font-medium text-lab underline">Open the calendar</Link>
        </div>
      ) : (
        <>
          <p className="text-sm text-muted">{a.posts_published} posts published, {a.posts_measured} with metrics so far.</p>
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-[var(--radius-card)] bg-line ring-1 ring-line sm:grid-cols-3 lg:grid-cols-6">
            {KPIS.map((k) => {
              const v = fmt(a.totals[k.key]);
              return (
                <div key={k.key} className="grid gap-1 bg-surface px-4 py-4">
                  <dt className="text-sm text-muted">{k.label}</dt>
                  <dd className={cn("display numeric", v === null ? "text-sm font-normal text-faint" : "text-3xl")}>{v ?? "Not available"}</dd>
                </div>
              );
            })}
          </dl>
          <section className="grid gap-3 rounded-[var(--radius-card)] bg-surface p-5 ring-1 ring-line">
            <h2 className="font-semibold">Engagements per day</h2>
            <Chart daily={a.daily} />
          </section>
          <section className="grid gap-3">
            <h2 className="font-semibold">By platform</h2>
            <div className="overflow-x-auto rounded-[var(--radius-card)] ring-1 ring-line">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <thead className="bg-sunk text-muted">
                  <tr>{["Platform", "Posts", "Reach", "Views", "Engagements", "Saves", "Not reported"].map((h) => <th key={h} scope="col" className="px-4 py-2.5 font-medium">{h}</th>)}</tr>
                </thead>
                <tbody className="bg-surface">
                  {a.platforms.map((p) => (
                    <tr key={p.platform} className="border-t border-line">
                      <th scope="row" className="px-4 py-2.5 font-medium">{PLATFORM_RULES[p.platform].label}</th>
                      <td className="numeric px-4 py-2.5">{p.posts}</td>
                      {(["reach", "views", "engagements", "saves"] as const).map((k) => (
                        <td key={k} className="numeric px-4 py-2.5">{fmt(p[k]) ?? <span className="text-xs text-faint">Not available</span>}</td>
                      ))}
                      <td className="px-4 py-2.5 text-xs text-muted">{p.unavailable.join(", ") || "None"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="grid gap-3">
            <h2 className="font-semibold">Top posts</h2>
            <ol className="divide-y divide-line overflow-hidden rounded-[var(--radius-card)] bg-surface ring-1 ring-line">
              {a.top_posts.map((t, i) => (
                <li key={`${t.content_id}-${t.platform}`} className="flex items-center gap-4 px-4 py-3 text-sm">
                  <span className="numeric w-5 text-muted">{i + 1}</span>
                  <Link href={`/content/${t.content_id}`} className="min-w-0 flex-1 truncate font-medium hover:underline">{t.title}</Link>
                  <span className="hidden text-muted sm:block">{PLATFORM_RULES[t.platform].label}{t.pillar ? `, ${PILLAR_LABELS[t.pillar] ?? t.pillar}` : ""}</span>
                  <span className="numeric w-28 text-right">{fmt(t.engagements)} engagements</span>
                  {t.url && <a href={t.url} target="_blank" rel="noreferrer" className="text-muted hover:text-ink" aria-label="Open on the platform"><ExternalLink className="size-4" /></a>}
                </li>
              ))}
            </ol>
          </section>
        </>
      )}
    </div>
  );
}
