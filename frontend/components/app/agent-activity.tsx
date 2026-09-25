"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { PageTitle } from "@/components/app/page-title";
import { useSession } from "@/components/app/session";
import { StatusChip } from "@/components/common/status";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { activityApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

const AGENTS: Record<string, string> = {
  content: "Content agent", publishing: "Publishing agent", analytics: "Analytics agent", strategy: "Strategy agent",
  research: "Research agent", creative: "Creative agent", optimization: "Optimization agent", orchestrator: "Marketing agent",
};

export function AgentActivity() {
  const { workspace } = useSession();
  const [agent, setAgent] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const runs = useQuery({ queryKey: ["agent-runs", workspace.id, agent], queryFn: () => activityApi.runs(workspace.id, agent || undefined), refetchInterval: 30_000 });
  return (
    <div className="mx-auto grid max-w-4xl gap-6">
      <PageTitle title="Agent activity" description="Everything your agents did for this business, step by step. Every run has limits on steps, time and cost."
        actions={<Select value={agent} onChange={(e) => setAgent(e.target.value)} className="h-10 w-52" aria-label="Agent"><option value="">All agents</option>{Object.entries(AGENTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>} />
      {runs.isPending ? <Skeleton className="h-64" /> : !runs.data?.length ? (
        <p className="text-muted">No agent work yet. Drafting a post, publishing and nightly analysis all appear here.</p>
      ) : (
        <ol className="relative grid gap-3 border-l border-line pl-6">
          {runs.data.map((r) => {
            const expanded = open === r.id;
            const when = r.started_at ? new Date(r.started_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "";
            return (
              <li key={r.id} className="relative">
                <span className={cn("absolute -left-[1.84rem] top-4 size-3 rounded-full ring-4 ring-paper", r.status === "failed" ? "bg-signal" : r.status === "running" ? "bg-marker" : "bg-lab")} aria-hidden />
                <article className="rounded-[var(--radius-card)] bg-surface ring-1 ring-line">
                  <button className="flex w-full items-start gap-3 p-4 text-left" onClick={() => setOpen(expanded ? null : r.id)} aria-expanded={expanded}>
                    <span className="grid min-w-0 flex-1 gap-0.5">
                      <span className="text-xs text-muted">{AGENTS[r.agent] ?? r.agent}, {when}{r.trigger === "user" ? ", started by you" : ""}</span>
                      <span className="font-medium">{r.goal}</span>
                      {r.summary && <span className="text-sm text-muted">{r.summary}</span>}
                    </span>
                    <StatusChip status={r.status} />
                    <ChevronDown className={cn("mt-1 size-4 text-muted transition-transform", expanded && "rotate-180")} aria-hidden />
                  </button>
                  {expanded && (
                    <div className="grid gap-3 border-t border-line px-4 py-3">
                      <ol className="grid gap-2">
                        {r.steps.map((s) => (
                          <li key={s.position} className="grid grid-cols-[1.5rem_1fr] gap-2 text-sm">
                            <span className="numeric text-muted">{s.position + 1}.</span>
                            <span>{s.title}{s.detail && <span className="block break-words text-xs text-muted">{s.detail}</span>}</span>
                          </li>
                        ))}
                      </ol>
                      <p className="numeric text-xs text-faint">{r.steps_taken} of {r.limits.max_steps} steps, ${r.cost_usd.toFixed(4)} of ${r.limits.max_cost_usd.toFixed(2)} cost limit{r.error ? `, error: ${r.error}` : ""}</p>
                    </div>
                  )}
                </article>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
