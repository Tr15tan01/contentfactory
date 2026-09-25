"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { PageTitle } from "@/components/app/page-title";
import { useSession } from "@/components/app/session";
import { StatusChip } from "@/components/common/status";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { contentApi } from "@/lib/api/endpoints";
import { dayKey, formatInZone, zonedParts, zonedToUtc } from "@/lib/zoned";
import { cn } from "@/lib/utils";
import type { ContentListItem, PlatformId } from "@/types/api";
import { PLATFORM_ORDER, PLATFORM_RULES } from "./meta";

type Day = { y: number; m: number; d: number; key: string };
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function addDays(day: Day, n: number): Day {
  const dt = new Date(Date.UTC(day.y, day.m - 1, day.d + n));
  const y = dt.getUTCFullYear(), m = dt.getUTCMonth() + 1, d = dt.getUTCDate();
  return { y, m, d, key: `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}` };
}

function weekday(day: Day): number {
  return (new Date(Date.UTC(day.y, day.m - 1, day.d)).getUTCDay() + 6) % 7; // Monday = 0
}

function Chip({ item, tz, compact }: { item: ContentListItem; tz: string; compact?: boolean }) {
  const draggable = !["publishing", "published", "generating"].includes(item.status);
  return (
    <Link
      href={`/content/${item.id}`}
      draggable={draggable}
      onDragStart={(e) => {
        e.dataTransfer.setData("text/content-id", item.id);
        e.dataTransfer.setData("text/scheduled-at", item.scheduled_at ?? "");
        e.dataTransfer.effectAllowed = "move";
      }}
      className={cn("grid min-w-0 gap-1 overflow-hidden rounded-md bg-surface px-2 py-1.5 text-left text-xs ring-1 ring-line hover:ring-lab", draggable && "cursor-grab active:cursor-grabbing")}
    >
      <span className="flex min-w-0 flex-col">
        {item.scheduled_at && <span className="numeric whitespace-nowrap text-muted">{formatInZone(item.scheduled_at, tz, { hour: "numeric", minute: "2-digit" })}</span>}
        <span className={cn("font-medium", compact ? "truncate" : "line-clamp-3")}>{item.title}</span>
      </span>
      {!compact && (
        <span className="grid justify-items-start gap-1">
          <span className="max-w-full truncate text-muted">{item.platforms.map((p) => PLATFORM_RULES[p].label).join(", ")}</span>
          <StatusChip status={item.status} className="px-1.5 py-0 text-[0.6875rem]" />
        </span>
      )}
    </Link>
  );
}

export function CalendarView() {
  const { workspace } = useSession();
  const ws = workspace.id;
  const tz = workspace.timezone;
  const queryClient = useQueryClient();
  const now = zonedParts(new Date(), tz);
  const today: Day = { y: now.year, m: now.month, d: now.day, key: dayKey(new Date(), tz) };
  const [view, setView] = useState<"month" | "week">("month");
  const [anchor, setAnchor] = useState<Day>(today);
  const [platform, setPlatform] = useState<PlatformId | "">("");
  const [dropError, setDropError] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);

  const days = useMemo(() => {
    if (view === "week") {
      const start = addDays(anchor, -weekday(anchor));
      return Array.from({ length: 7 }, (_, i) => addDays(start, i));
    }
    const first: Day = addDays({ ...anchor, d: 1, key: "" }, 0);
    const start = addDays(first, -weekday(first));
    return Array.from({ length: 42 }, (_, i) => addDays(start, i));
  }, [view, anchor]);

  const rangeStart = zonedToUtc(days[0]!.y, days[0]!.m, days[0]!.d, 0, 0, tz).toISOString();
  const last = addDays(days[days.length - 1]!, 1);
  const rangeEnd = zonedToUtc(last.y, last.m, last.d, 0, 0, tz).toISOString();

  const scheduled = useQuery({
    queryKey: ["content", ws, { calendar: rangeStart, platform }],
    queryFn: () => contentApi.list(ws, { start: rangeStart, end: rangeEnd, platform: platform || undefined, limit: 500 }),
  });
  const unscheduled = useQuery({
    queryKey: ["content", ws, { unscheduled: true }],
    queryFn: () => contentApi.list(ws, { unscheduled: true, status: ["ready", "draft", "awaiting_approval", "approved", "rejected"], limit: 30 }),
  });

  const byDay = useMemo(() => {
    const map = new Map<string, ContentListItem[]>();
    for (const item of scheduled.data?.items ?? []) {
      if (!item.scheduled_at) continue;
      const k = dayKey(new Date(item.scheduled_at), tz);
      map.set(k, [...(map.get(k) ?? []), item]);
    }
    return map;
  }, [scheduled.data, tz]);

  const reschedule = useMutation({
    mutationFn: ({ id, iso }: { id: string; iso: string }) => contentApi.schedule(ws, id, iso),
    onSuccess: () => {
      setDropError(null);
      void queryClient.invalidateQueries({ queryKey: ["content", ws] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard", ws] });
    },
    onError: (e) => setDropError(e instanceof ApiError ? e.message : "The post couldn't be moved."),
  });

  const onDrop = (day: Day, e: React.DragEvent) => {
    e.preventDefault();
    setOver(null);
    const id = e.dataTransfer.getData("text/content-id");
    if (!id) return;
    const prev = e.dataTransfer.getData("text/scheduled-at");
    const t = prev ? zonedParts(new Date(prev), tz) : { hour: 10, minute: 0 };
    if (day.key < today.key) return setDropError("That day has passed. Drop the post on today or later.");
    reschedule.mutate({ id, iso: zonedToUtc(day.y, day.m, day.d, t.hour, t.minute, tz).toISOString() });
  };

  const title =
    view === "month"
      ? new Date(Date.UTC(anchor.y, anchor.m - 1, 15)).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
      : `Week of ${new Date(Date.UTC(days[0]!.y, days[0]!.m - 1, days[0]!.d)).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })}`;
  const step = (dir: 1 | -1) =>
    setAnchor(view === "week" ? addDays(anchor, 7 * dir) : addDays({ ...anchor, d: 1, key: "" }, dir === 1 ? 32 : -1));

  return (
    <div className="mx-auto max-w-7xl">
      <PageTitle
        title="Calendar"
        description={`Drag a post to another day to move it. Times are in ${tz.replaceAll("_", " ")}.`}
        actions={workspace.role !== "viewer" && <Button asChild><Link href="/content/new"><Plus /> Create post</Link></Button>}
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => step(-1)} aria-label="Previous"><ChevronLeft className="size-4" /></Button>
          <Button variant="ghost" size="icon" onClick={() => step(1)} aria-label="Next"><ChevronRight className="size-4" /></Button>
          <Button variant="secondary" size="sm" onClick={() => setAnchor(today)}>Today</Button>
        </div>
        <h2 className="text-lg font-semibold" aria-live="polite">{title}</h2>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Select value={platform} onChange={(e) => setPlatform(e.target.value as PlatformId | "")} className="h-9 w-40 text-sm" aria-label="Platform">
            <option value="">All platforms</option>
            {PLATFORM_ORDER.filter((p) => PLATFORM_RULES[p].available).map((p) => <option key={p} value={p}>{PLATFORM_RULES[p].label}</option>)}
          </Select>
          <div role="radiogroup" aria-label="View" className="inline-flex rounded-[var(--radius-control)] bg-sunk p-1 text-sm">
            {(["month", "week"] as const).map((v) => (
              <button key={v} role="radio" aria-checked={view === v} onClick={() => setView(v)} className={cn("rounded-[7px] px-3 py-1 capitalize text-muted", view === v && "bg-surface font-medium text-ink shadow-sm")}>{v}</button>
            ))}
          </div>
        </div>
      </div>
      {dropError && <Alert tone="error" title="Not moved" className="mb-4">{dropError}</Alert>}

      <div className="grid items-start gap-6 xl:grid-cols-[1fr_15rem]">
        <div className="overflow-hidden rounded-[var(--radius-card)] ring-1 ring-line">
          <div className="grid grid-cols-[repeat(7,minmax(0,1fr))] border-b border-line bg-sunk text-xs font-medium text-muted">
            {WEEKDAYS.map((d) => <div key={d} className="px-2 py-2">{d}</div>)}
          </div>
          <div className="grid grid-cols-[repeat(7,minmax(0,1fr))]">
            {days.map((day) => {
              const items = byDay.get(day.key) ?? [];
              const outside = view === "month" && day.m !== anchor.m;
              const past = day.key < today.key;
              return (
                <div
                  key={day.key}
                  data-day={day.key}
                  onDragOver={(e) => { if (!past) { e.preventDefault(); setOver(day.key); } }}
                  onDragLeave={() => setOver((o) => (o === day.key ? null : o))}
                  onDrop={(e) => onDrop(day, e)}
                  className={cn(
                    "grid min-w-0 content-start gap-1 border-b border-r border-line bg-surface p-1.5 [&:nth-child(7n)]:border-r-0",
                    view === "month" ? "min-h-28" : "min-h-80",
                    (outside || past) && "bg-sunk/50",
                    over === day.key && "bg-lab-soft ring-2 ring-inset ring-lab",
                  )}
                >
                  <span className={cn("numeric px-1 text-xs", day.key === today.key ? "font-semibold text-lab" : outside ? "text-faint" : "text-muted")}>
                    {day.d}
                  </span>
                  {items.slice(0, view === "month" ? 3 : 20).map((item) => <Chip key={item.id} item={item} tz={tz} compact={view === "month"} />)}
                  {view === "month" && items.length > 3 && <span className="px-1 text-xs text-muted">+{items.length - 3} more</span>}
                </div>
              );
            })}
          </div>
        </div>

        <aside className="grid gap-3">
          <h2 className="text-sm font-semibold">Not scheduled</h2>
          <p className="text-xs text-muted">Drag onto a day to schedule at 10:00.</p>
          {unscheduled.data?.items.length ? (
            unscheduled.data.items.map((item) => <Chip key={item.id} item={item} tz={tz} />)
          ) : (
            <p className="text-sm text-muted">Everything is on the calendar.</p>
          )}
        </aside>
      </div>
      {scheduled.isFetching && <p className="sr-only" role="status">Loading calendar</p>}
    </div>
  );
}
