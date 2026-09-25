"use client";

import { useDeferredValue, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Plus, Search } from "lucide-react";
import { PageTitle } from "@/components/app/page-title";
import { useSession } from "@/components/app/session";
import { contentTypeName, StatusChip } from "@/components/common/status";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { contentApi } from "@/lib/api/endpoints";
import { formatInZone } from "@/lib/zoned";
import { cn } from "@/lib/utils";
import type { ContentStatus } from "@/types/api";
import { PLATFORM_RULES } from "./meta";

const TABS: { id: string; label: string; status?: ContentStatus[] }[] = [
  { id: "all", label: "All" },
  { id: "approval", label: "Needs approval", status: ["awaiting_approval", "ready"] },
  { id: "scheduled", label: "Approved and scheduled", status: ["approved", "scheduled"] },
  { id: "drafts", label: "Drafts", status: ["draft", "generating"] },
  { id: "attention", label: "Rejected or failed", status: ["rejected", "failed"] },
];

export function ContentList() {
  const { workspace } = useSession();
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const status = TABS.find((t) => t.id === tab)?.status;
  const list = useQuery({
    queryKey: ["content", workspace.id, { tab, q }],
    queryFn: () => contentApi.list(workspace.id, { status, q: q || undefined }),
    refetchInterval: (query) => (query.state.data?.items.some((i) => i.status === "generating") ? 2000 : false),
  });

  return (
    <div className="mx-auto max-w-6xl">
      <PageTitle title="Content" description="Every post for this business, from first draft to approved." actions={workspace.role !== "viewer" && <Button asChild><Link href="/content/new"><Plus /> Create post</Link></Button>} />
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div role="tablist" className="flex flex-wrap gap-1 rounded-[var(--radius-control)] bg-sunk p-1 text-sm">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)} className={cn("rounded-[7px] px-3 py-1.5 text-muted", tab === t.id && "bg-surface font-medium text-ink shadow-sm")}>{t.label}</button>
          ))}
        </div>
        <label className="relative ml-auto min-w-56">
          <span className="sr-only">Search posts</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" aria-hidden />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search posts" className="h-10 pl-9" />
        </label>
      </div>

      {list.isPending ? (
        <div className="grid gap-2">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : list.error ? (
        <Alert tone="error" title="Posts didn't load">{list.error instanceof ApiError ? list.error.message : "Try again."}</Alert>
      ) : !list.data.items.length ? (
        <div className="grid justify-items-start gap-3 rounded-[var(--radius-card)] border border-dashed border-line-strong bg-surface/60 px-6 py-12">
          <h2 className="text-lg font-semibold">{tab === "all" && !q ? "No posts yet" : "Nothing here"}</h2>
          <p className="max-w-lg text-muted">{tab === "all" && !q ? "Ask your agent for a first draft. It writes from your business profile and picks photos from your library." : "Try another tab or search."}</p>
          {tab === "all" && !q && workspace.role !== "viewer" && <Button asChild><Link href="/content/new"><Plus /> Create post</Link></Button>}
        </div>
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-[var(--radius-card)] bg-surface ring-1 ring-line">
          {list.data.items.map((item) => (
            <li key={item.id}>
              <Link href={`/content/${item.id}`} className="flex items-center gap-4 px-4 py-3 hover:bg-sunk/50">
                <span className="size-12 shrink-0 overflow-hidden rounded-md bg-sunk">
                  {/* eslint-disable-next-line @next/next/no-img-element -- signed storage URL */}
                  {item.thumbnail_url && <img src={item.thumbnail_url} alt="" className="size-full object-cover" loading="lazy" />}
                </span>
                <span className="grid min-w-0 flex-1 gap-0.5">
                  <span className="truncate font-medium">{item.title}</span>
                  <span className="truncate text-sm text-muted">{contentTypeName(item.content_type)} for {item.platforms.map((p) => PLATFORM_RULES[p].label).join(", ")}</span>
                </span>
                {item.warnings > 0 && <AlertTriangle className="size-4 shrink-0 text-caution" aria-label={`${item.warnings} warnings`} />}
                <span className="hidden w-40 text-right text-sm text-muted sm:block">
                  {item.scheduled_at ? formatInZone(item.scheduled_at, workspace.timezone, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "Not scheduled"}
                </span>
                <StatusChip status={item.status} className="shrink-0" />
              </Link>
            </li>
          ))}
        </ul>
      )}
      {list.data && list.data.total > list.data.items.length && <p className="mt-3 text-sm text-muted">Showing {list.data.items.length} of {list.data.total}. Search to narrow down.</p>}
    </div>
  );
}
