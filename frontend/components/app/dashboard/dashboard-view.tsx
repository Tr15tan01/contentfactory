"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "motion/react";
import { AlertTriangle, ArrowUpRight, Bot, CalendarClock, CircleDot, Link2, PenLine, Plus, Sparkles } from "lucide-react";
import { contentTypeName, platformName, StatusChip } from "@/components/common/status";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { workspaceApi } from "@/lib/api/endpoints";
import { cn, formatNumber } from "@/lib/utils";
import type { AgentActivity, AttentionItem, Dashboard, LearnedInsight, UpcomingItem } from "@/types/api";
import { useSession } from "../session";

// Matches MIN_INSIGHT_SAMPLE in backend/app/services/dashboard.py
const MIN_INSIGHT_SAMPLE = 8;

function greeting(timezone: string): string {
  const hour = Number(new Intl.DateTimeFormat("en-US", { hour: "numeric", hourCycle: "h23", timeZone: timezone }).format(new Date()));
  if (hour < 5) return "Working late";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function when(iso: string, timezone: string): { day: string; time: string } {
  const d = new Date(iso);
  const dayKey = (x: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: timezone }).format(x);
  const today = dayKey(new Date());
  const tomorrow = dayKey(new Date(Date.now() + 86_400_000));
  const key = dayKey(d);
  const day =
    key === today
      ? "Today"
      : key === tomorrow
        ? "Tomorrow"
        : new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: timezone }).format(d);
  const time = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: timezone }).format(d);
  return { day, time };
}

function ago(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

function Panel({ title, action, children, className }: { title: string; action?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("grid content-start gap-4 rounded-[var(--radius-card)] bg-surface p-5 ring-1 ring-line", className)}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

const attentionIcon: Record<AttentionItem["kind"], typeof AlertTriangle> = {
  finish_onboarding: Sparkles,
  approve_content: PenLine,
  approval_overdue: CalendarClock,
  publication_failed: AlertTriangle,
  renew_connection: Link2,
  connect_account: Link2,
};

function Attention({ items }: { items: AttentionItem[] }) {
  if (!items.length) return null;
  return (
    <section aria-labelledby="attention-title" className="grid gap-3">
      <h2 id="attention-title" className="text-sm font-medium text-muted">
        Needs your attention <span className="numeric">({items.length})</span>
      </h2>
      <ul className="grid overflow-hidden rounded-[var(--radius-card)] bg-surface ring-1 ring-line">
        {items.map((item, i) => {
          const Icon = attentionIcon[item.kind];
          return (
            <li key={`${item.kind}-${i}`} className="border-b border-line last:border-b-0">
              <Link href={item.action_url} className="group flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-sunk/60">
                <span
                  className={cn(
                    "grid size-9 shrink-0 place-items-center rounded-full",
                    item.priority === "high" ? "bg-signal-soft text-signal" : "bg-marker-soft text-ink dark:text-marker",
                    item.kind === "finish_onboarding" && "bg-lab-soft text-lab",
                  )}
                >
                  <Icon className="size-4" aria-hidden />
                </span>
                <span className="grid min-w-0 flex-1">
                  <span className="font-medium">{item.title}</span>
                  <span className="truncate text-sm text-muted">{item.description}</span>
                </span>
                <ArrowUpRight className="size-4 shrink-0 text-faint transition-colors group-hover:text-ink" aria-hidden />
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function WeekStrip({ week }: { week: Dashboard["week"] }) {
  const stats = [
    { label: "Created", value: week.created },
    { label: "Published", value: week.published },
    { label: "Scheduled", value: week.scheduled },
    { label: "Awaiting approval", value: week.awaiting_approval, highlight: week.awaiting_approval > 0 },
  ];
  return (
    <section aria-label="This week" className="grid gap-3">
      <h2 className="text-sm font-medium text-muted">This week</h2>
      <dl className="grid grid-cols-2 overflow-hidden rounded-[var(--radius-card)] bg-surface ring-1 ring-line md:grid-cols-4">
        {stats.map((s, i) => (
          <div key={s.label} className={cn("grid gap-1 px-5 py-4", i > 0 && "md:border-l", i % 2 === 1 && "border-l", i > 1 && "border-t md:border-t-0", "border-line")}>
            <dt className="text-sm text-muted">{s.label}</dt>
            <dd className={cn("display numeric text-4xl", s.highlight && "text-lab")}>{s.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Upcoming({ items, timezone }: { items: UpcomingItem[]; timezone: string }) {
  return (
    <Panel title="Upcoming" action={<Link href="/calendar" className="text-sm text-lab hover:underline">Open calendar</Link>}>
      {items.length === 0 ? (
        <div className="grid justify-items-start gap-3 py-4">
          <p className="text-muted">Nothing is scheduled yet. Create a post, or finish setup and your agent will draft your first week.</p>
          <Button asChild size="sm" variant="secondary"><Link href="/content/new"><Plus /> Create post</Link></Button>
        </div>
      ) : (
        <ol className="grid">
          {items.map((item) => {
            const t = when(item.scheduled_at, timezone);
            return (
              <li key={item.content_id}>
                <Link href={`/content/${item.content_id}`} className="grid grid-cols-[5.5rem_1fr] gap-4 rounded-md border-t border-line py-3 first:border-t-0 hover:bg-sunk/50">
                  <span className="grid content-start pl-1">
                    <span className="text-sm font-medium">{t.day}</span>
                    <span className="numeric text-sm text-muted">{t.time}</span>
                  </span>
                  <span className="grid min-w-0 gap-1">
                    <span className="truncate font-medium">{item.title}</span>
                    <span className="flex flex-wrap items-center gap-2 text-sm text-muted">
                      {platformName(item.platform)} {contentTypeName(item.content_type).toLowerCase()}
                      <StatusChip status={item.status} />
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}

const agentNames: Record<string, string> = {
  orchestrator: "Marketing agent",
  strategy: "Strategy agent",
  research: "Research agent",
  content: "Content agent",
  creative: "Creative agent",
  publishing: "Publishing agent",
  analytics: "Analytics agent",
  optimization: "Optimization agent",
};

function AgentPanel({ runs }: { runs: AgentActivity[] }) {
  const working = runs.find((r) => r.status === "running");
  return (
    <Panel title="Your agent" action={<Link href="/agent" className="text-sm text-lab hover:underline">Activity</Link>}>
      <div className="flex items-center gap-3 rounded-[var(--radius-control)] bg-sunk/70 px-3.5 py-3">
        <Bot className="size-5 text-lab" aria-hidden />
        <p className="text-sm">
          {working ? (
            <>
              <span className="font-medium">Working:</span> {working.latest_step ?? working.goal}
            </>
          ) : runs.length ? (
            "Idle. Next run starts on schedule or when you ask."
          ) : (
            "Not started yet. It begins once your business profile is set up."
          )}
        </p>
      </div>
      {runs.length > 0 && (
        <ul className="grid gap-3">
          {runs.map((run) => (
            <li key={run.run_id} className="grid grid-cols-[auto_1fr] gap-3">
              <CircleDot className={cn("mt-1 size-3.5", run.status === "running" ? "text-lab" : "text-faint")} aria-hidden />
              <div className="grid gap-0.5">
                <p className="text-sm">
                  <span className="font-medium">{agentNames[run.agent] ?? run.agent}</span>{" "}
                  <span className="text-muted">{run.goal}</span>
                </p>
                <p className="flex items-center gap-2 text-xs text-muted">
                  <StatusChip status={run.status} /> {ago(run.updated_at)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Learned({ items }: { items: LearnedInsight[] }) {
  const fmt = (d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return (
    <Panel title="What your agent learned" action={<Link href="/insights" className="text-sm text-lab hover:underline">All insights</Link>}>
      {items.length === 0 ? (
        <p className="text-sm text-muted">
          No conclusions yet. Insights appear once at least {MIN_INSIGHT_SAMPLE} published posts have performance data, so
          they&apos;re based on evidence rather than a lucky post.
        </p>
      ) : (
        <ul className="grid gap-4">
          {items.map((insight) => (
            <li key={insight.id} className="grid gap-1.5">
              <p className="leading-snug"><span className="marker">{insight.statement}</span></p>
              <p className="text-xs text-muted">
                {insight.sample_size} posts, {fmt(insight.period_start)} to {fmt(insight.period_end)}
                {insight.platform ? `, ${platformName(insight.platform)}` : ""}. Confidence: {insight.confidence}.
              </p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Performance({ perf }: { perf: Dashboard["performance"] }) {
  const cells = [
    { label: "Reach", value: perf.reach },
    { label: "Views", value: perf.views },
    { label: "Engagements", value: perf.engagements },
  ];
  return (
    <Panel title={`Performance, last ${perf.period_days} days`} action={<Link href="/analytics" className="text-sm text-lab hover:underline">Analytics</Link>}>
      {perf.posts_measured === 0 ? (
        <p className="text-sm text-muted">No published posts have performance data yet. Numbers appear here after your first posts go live.</p>
      ) : (
        <>
          <dl className="grid grid-cols-3 gap-4">
            {cells.map((c) => (
              <div key={c.label} className="grid gap-0.5">
                <dt className="text-sm text-muted">{c.label}</dt>
                <dd className="display numeric text-3xl">{c.value === null ? <span className="text-base font-normal text-muted">Not available</span> : formatNumber(c.value)}</dd>
              </div>
            ))}
          </dl>
          <p className="text-xs text-muted">From {perf.posts_measured} measured {perf.posts_measured === 1 ? "post" : "posts"}, as reported by each platform.</p>
        </>
      )}
    </Panel>
  );
}

function DashboardSkeleton() {
  return (
    <div className="grid gap-6" aria-busy="true" aria-label="Loading dashboard">
      <Skeleton className="h-10 w-72" />
      <Skeleton className="h-28" />
      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Skeleton className="h-72" />
        <Skeleton className="h-72" />
      </div>
    </div>
  );
}

export function DashboardView() {
  const { user, workspace } = useSession();
  const reduce = useReducedMotion();
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["dashboard", workspace.id],
    queryFn: () => workspaceApi.dashboard(workspace.id),
    refetchInterval: 60_000,
  });

  if (isPending) return <DashboardSkeleton />;
  if (error || !data) {
    return (
      <Alert tone="error" title="The dashboard didn't load">
        {error instanceof ApiError ? error.message : "Try again in a moment."}{" "}
        <button className="underline" onClick={() => void refetch()}>Retry</button>
      </Alert>
    );
  }

  const firstName = user.full_name?.split(" ")[0];
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.2, 0.7, 0.2, 1] }}
      className="mx-auto grid max-w-6xl gap-8"
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="grid gap-1">
          <h1 className="display text-3xl sm:text-4xl">
            {greeting(user.timezone || workspace.timezone)}
            {firstName ? `, ${firstName}` : ""}
          </h1>
          <p className="text-muted">
            {data.business_name}
            {data.is_demo && <span className="ml-2 rounded-full bg-marker-soft px-2 py-0.5 text-xs font-medium text-ink dark:text-marker">Demo data</span>}
          </p>
        </div>
        <Button asChild className="sm:hidden"><Link href="/content/new"><Plus /> Create post</Link></Button>
      </div>

      <Attention items={data.attention} />
      <WeekStrip week={data.week} />

      <div className="grid items-start gap-6 xl:grid-cols-[1.4fr_1fr]">
        <div className="grid gap-6">
          <Upcoming items={data.upcoming} timezone={workspace.timezone} />
          <Performance perf={data.performance} />
        </div>
        <div className="grid gap-6">
          <AgentPanel runs={data.agent} />
          <Learned items={data.learned} />
        </div>
      </div>
    </motion.div>
  );
}
