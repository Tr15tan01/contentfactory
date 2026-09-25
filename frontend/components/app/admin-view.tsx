"use client";

import { useDeferredValue, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { PageTitle } from "@/components/app/page-title";
import { useSession } from "@/components/app/session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { adminApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

export function AdminView() {
  const { user } = useSession();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const overview = useQuery({ queryKey: ["admin-overview"], queryFn: adminApi.overview, enabled: user.is_superuser });
  const users = useQuery({ queryKey: ["admin-users", q], queryFn: () => adminApi.users(q || undefined), enabled: user.is_superuser });
  const audit = useQuery({ queryKey: ["admin-audit"], queryFn: () => adminApi.audit(), enabled: user.is_superuser });
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["admin-users"] }); void qc.invalidateQueries({ queryKey: ["admin-audit"] }); };
  const suspend = useMutation({ mutationFn: ({ id, reason }: { id: string; reason: string }) => adminApi.suspend(id, reason), onSuccess: refresh });
  const unsuspend = useMutation({ mutationFn: adminApi.unsuspend, onSuccess: refresh });

  if (!user.is_superuser) return <Alert tone="error" title="Not available">This area is for ContentFactory administrators.</Alert>;
  const o = overview.data;
  const stats = o ? [
    ["Users", o.users], ["New this week", o.signups_7d], ["Businesses", o.workspaces], ["MRR", `$${o.mrr_usd.toLocaleString("en-US")}`],
    ["AI calls, 30 days", o.ai_calls_30d], ["AI cost, 30 days", `$${o.ai_cost_usd_30d.toFixed(2)}`],
    ["Published, 7 days", o.publications_7d.published ?? 0], ["Failed, 7 days", o.publications_7d.failed ?? 0],
  ] as const : [];
  return (
    <div className="mx-auto grid max-w-6xl gap-8">
      <PageTitle title="Admin" description="Platform health, customers and the audit log. Every action here is recorded." />
      {suspend.error && <Alert tone="error" title="Not suspended">{suspend.error instanceof ApiError ? suspend.error.message : "Try again."}</Alert>}
      {!o ? <Skeleton className="h-28" /> : (
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-[var(--radius-card)] bg-line ring-1 ring-line md:grid-cols-4">
          {stats.map(([k, v]) => <div key={k} className="grid gap-1 bg-surface px-4 py-3"><dt className="text-sm text-muted">{k}</dt><dd className="display numeric text-2xl">{v}</dd></div>)}
        </dl>
      )}
      {o && <p className="text-sm text-muted">Plans: {Object.entries(o.plans).map(([k, v]) => `${k} ${v}`).join(", ")}. MRR counts active Paddle subscriptions only (manual plans excluded).</p>}
      <section className="grid gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Customers</h2>
          <label className="relative w-72"><span className="sr-only">Search customers</span><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" aria-hidden /><Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Email or name" className="h-10 pl-9" /></label>
        </div>
        <div className="overflow-x-auto rounded-[var(--radius-card)] ring-1 ring-line">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <thead className="bg-sunk text-muted"><tr>{["Customer", "Plan", "Status", "Joined", "Last sign-in", ""].map((h) => <th key={h} scope="col" className="px-4 py-2.5 font-medium">{h}</th>)}</tr></thead>
            <tbody className="bg-surface">
              {users.data?.map((u) => (
                <tr key={u.id} className="border-t border-line">
                  <td className="px-4 py-2.5"><span className="block font-medium">{u.email}</span><span className="text-xs text-muted">{u.full_name}</span></td>
                  <td className="px-4 py-2.5 capitalize">{u.plan}</td>
                  <td className="px-4 py-2.5"><span className={cn("rounded-full px-2 py-0.5 text-xs", u.status === "suspended" ? "bg-signal-soft text-signal" : u.status === "active" ? "bg-lab-soft text-lab" : "bg-sunk text-muted")} title={u.suspended_reason ?? undefined}>{u.status}</span></td>
                  <td className="px-4 py-2.5 text-muted">{new Date(u.created_at).toLocaleDateString("en-US", { dateStyle: "medium" })}</td>
                  <td className="px-4 py-2.5 text-muted">{u.last_login_at ? new Date(u.last_login_at).toLocaleDateString("en-US", { dateStyle: "medium" }) : "Never"}</td>
                  <td className="px-4 py-2.5 text-right">
                    {u.is_superuser ? <span className="text-xs text-muted">Admin</span> : u.status === "suspended" ? (
                      <Button size="sm" variant="secondary" onClick={() => unsuspend.mutate(u.id)}>Restore</Button>
                    ) : (
                      <Button size="sm" variant="ghost" className="text-signal" onClick={() => { const reason = window.prompt(`Why suspend ${u.email}? This is recorded.`); if (reason && reason.trim().length >= 3) suspend.mutate({ id: u.id, reason: reason.trim() }); }}>Suspend</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="grid gap-3">
        <h2 className="text-lg font-semibold">Audit log</h2>
        <ol className="divide-y divide-line overflow-hidden rounded-[var(--radius-card)] bg-surface text-sm ring-1 ring-line">
          {audit.data?.slice(0, 50).map((a) => (
            <li key={a.id} className="grid gap-1 px-4 py-2.5 sm:grid-cols-[11rem_14rem_1fr]">
              <span className="numeric text-muted">{new Date(a.created_at).toLocaleString("en-US", { dateStyle: "short", timeStyle: "short" })}</span>
              <span className="font-medium">{a.action}</span>
              <span className="truncate text-muted">{a.actor ?? "system"}{a.ip_address ? `, ${a.ip_address}` : ""}</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
