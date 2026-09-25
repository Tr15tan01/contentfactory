"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus, Check, FlaskConical, Plus, RefreshCw, X } from "lucide-react";
import { PageTitle } from "@/components/app/page-title";
import { useSession } from "@/components/app/session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { contentApi, intelligenceApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";
import type { Experiment, Insight } from "@/types/api";

const errText = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong. Try again.");
const date = (d: string) => new Date(`${d.slice(0, 10)}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric" });

function InsightCard({ insight, ws, canEdit }: { insight: Insight; ws: string; canEdit: boolean }) {
  const qc = useQueryClient();
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["insights", ws] }); void qc.invalidateQueries({ queryKey: ["memory", ws] }); };
  const remember = useMutation({ mutationFn: () => intelligenceApi.remember(ws, insight.id), onSuccess: refresh });
  const dismiss = useMutation({ mutationFn: () => intelligenceApi.dismiss(ws, insight.id), onSuccess: refresh });
  const groups = Object.entries(insight.evidence.groups ?? {}).sort((a, b) => b[1].mean - a[1].mean);
  const max = Math.max(1, ...groups.map(([, g]) => g.mean));
  const saved = !!insight.evidence.memory_id;
  return (
    <article className="grid gap-4 rounded-[var(--radius-card)] bg-surface p-5 ring-1 ring-line">
      <p className="text-lg font-medium leading-snug"><span className="marker">{insight.statement}</span></p>
      {groups.length > 0 && (
        <div className="grid gap-1.5" role="img" aria-label={`Average ${insight.metric} per group`}>
          {groups.map(([name, g]) => (
            <div key={name} className="grid grid-cols-[8rem_1fr_5rem] items-center gap-3 text-sm">
              <span className="truncate capitalize text-muted">{name.replaceAll("_", " ")}</span>
              <span className="h-2.5 rounded-full bg-sunk"><span className={cn("block h-full rounded-full", name === insight.segment_a ? "bg-lab" : "bg-line-strong")} style={{ width: `${(g.mean / max) * 100}%` }} /></span>
              <span className="numeric text-right text-xs text-muted">{Math.round(g.mean)} ({g.n} posts)</span>
            </div>
          ))}
        </div>
      )}
      <p className="text-xs text-muted">
        Based on {insight.sample_size} posts ({insight.evidence.n_a} vs {insight.evidence.n_b}), {date(insight.period_start)} to {date(insight.period_end)}. Confidence: {insight.confidence}.
      </p>
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          {saved ? (
            <span className="inline-flex items-center gap-1.5 text-sm text-lab"><Check className="size-4" /> In your agent&apos;s memory</span>
          ) : (
            <Button size="sm" onClick={() => remember.mutate()} loading={remember.isPending}><BookmarkPlus /> Remember this</Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => dismiss.mutate()} loading={dismiss.isPending}><X /> Not useful</Button>
        </div>
      )}
    </article>
  );
}

const VARIABLES = [["hook", "Hook"], ["cta", "Call to action"], ["format", "Format"], ["time", "Posting time"], ["topic", "Topic"], ["visual", "Visual"]] as const;
const METRICS = [["engagements", "Engagements"], ["saves", "Saves"], ["reach", "Reach"], ["views", "Views"], ["comments", "Comments"], ["shares", "Shares"]] as const;

function NewExperiment({ ws, onDone }: { ws: string; onDone: () => void }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ name: "", hypothesis: "", variable: "hook", primary_metric: "engagements", variant_a: "", variant_b: "", min_sample_per_variant: 5 });
  const create = useMutation({
    mutationFn: () => intelligenceApi.createExperiment(ws, f),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["experiments", ws] }); onDone(); },
  });
  const set = (k: keyof typeof f, v: string | number) => setF((x) => ({ ...x, [k]: v }));
  return (
    <form className="mt-5 grid gap-4" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
      {create.error && <Alert tone="error" title="Not created">{errText(create.error)}</Alert>}
      <Field id="exp-name" label="Name"><Input value={f.name} onChange={(e) => set("name", e.target.value)} required minLength={3} placeholder="Question hooks vs statements" /></Field>
      <Field id="exp-hyp" label="What do you expect?"><Textarea value={f.hypothesis} onChange={(e) => set("hypothesis", e.target.value)} required rows={2} className="min-h-16" placeholder="Hooks phrased as questions get more comments." /></Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field id="exp-var" label="Testing"><Select value={f.variable} onChange={(e) => set("variable", e.target.value)}>{VARIABLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
        <Field id="exp-metric" label="Judged by"><Select value={f.primary_metric} onChange={(e) => set("primary_metric", e.target.value)}>{METRICS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
        <Field id="exp-min" label="Posts per side"><Input type="number" min={3} max={50} value={f.min_sample_per_variant} onChange={(e) => set("min_sample_per_variant", Number(e.target.value))} /></Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="exp-a" label="Variant A"><Input value={f.variant_a} onChange={(e) => set("variant_a", e.target.value)} required placeholder="Hook is a question" /></Field>
        <Field id="exp-b" label="Variant B"><Input value={f.variant_b} onChange={(e) => set("variant_b", e.target.value)} required placeholder="Hook is a statement" /></Field>
      </div>
      <div className="flex justify-end"><Button type="submit" loading={create.isPending}>Start experiment</Button></div>
    </form>
  );
}

function ChoosePosts({ ws, exp, label, onDone }: { ws: string; exp: Experiment; label: string; onDone: () => void }) {
  const qc = useQueryClient();
  const variant = exp.variants.find((v) => v.label === label)!;
  const other = exp.variants.find((v) => v.label !== label)!;
  const [picked, setPicked] = useState<string[]>(variant.content_ids);
  const posts = useQuery({ queryKey: ["content", ws, { experiment: true }], queryFn: () => contentApi.list(ws, { limit: 200 }) });
  const save = useMutation({ mutationFn: () => intelligenceApi.assign(ws, exp.id, label, picked), onSuccess: () => { void qc.invalidateQueries({ queryKey: ["experiments", ws] }); onDone(); } });
  return (
    <div className="mt-5 grid gap-4">
      {save.error && <Alert tone="error" title="Not saved">{errText(save.error)}</Alert>}
      <ul className="max-h-[50vh] divide-y divide-line overflow-y-auto border-y border-line">
        {posts.data?.items.filter((p) => !other.content_ids.includes(p.id)).map((p) => (
          <li key={p.id}>
            <label className="flex items-center gap-3 py-2.5 text-sm">
              <input type="checkbox" className="size-4 accent-[var(--lab)]" checked={picked.includes(p.id)} onChange={(e) => setPicked(e.target.checked ? [...picked, p.id] : picked.filter((x) => x !== p.id))} />
              <span className="min-w-0 flex-1 truncate">{p.title}</span>
              <span className="text-xs text-muted">{p.status.replaceAll("_", " ")}</span>
            </label>
          </li>
        ))}
      </ul>
      <div className="flex justify-end"><Button onClick={() => save.mutate()} loading={save.isPending}>Use {picked.length} posts</Button></div>
    </div>
  );
}

function ExperimentCard({ exp, ws, canEdit }: { exp: Experiment; ws: string; canEdit: boolean }) {
  const qc = useQueryClient();
  const [choosing, setChoosing] = useState<string | null>(null);
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["experiments", ws] }); void qc.invalidateQueries({ queryKey: ["memory", ws] }); };
  const evaluate = useMutation({ mutationFn: () => intelligenceApi.evaluate(ws, exp.id), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: () => intelligenceApi.cancel(ws, exp.id), onSuccess: refresh });
  const running = exp.status === "running";
  return (
    <article className="grid gap-4 rounded-[var(--radius-card)] bg-surface p-5 ring-1 ring-line">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-0.5">
          <h3 className="font-semibold">{exp.name}</h3>
          <p className="text-sm text-muted">{exp.hypothesis}</p>
        </div>
        <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", exp.status === "completed" ? "bg-lab-soft text-lab" : running ? "bg-marker-soft text-ink dark:text-marker" : "bg-sunk text-muted")}>
          {{ running: "Running", completed: "Winner found", inconclusive: "No clear winner", cancelled: "Cancelled", draft: "Draft" }[exp.status]}
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {exp.variants.map((v) => (
          <div key={v.id} className={cn("grid gap-1 rounded-[var(--radius-control)] p-3 ring-1 ring-line", exp.winner_variant_id === v.id && "bg-lab-soft/60 ring-lab")}>
            <p className="text-sm font-medium">{v.label}: {v.description}</p>
            <p className="numeric text-xs text-muted">
              {v.content_ids.length} posts assigned, {v.sample_size} measured
              {v.metrics.mean != null ? `, ${Math.round(v.metrics.mean)} ${exp.primary_metric} per post` : ""}
            </p>
            {running && canEdit && <button className="justify-self-start text-xs text-lab underline" onClick={() => setChoosing(v.label)}>Choose posts</button>}
          </div>
        ))}
      </div>
      {exp.conclusion && <p className="text-sm">{exp.conclusion}</p>}
      {running && exp.result.enough_data === false && <p className="text-sm text-muted">Still collecting: each side needs {exp.min_sample_per_variant} published posts with metrics.</p>}
      {running && canEdit && (
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={() => evaluate.mutate()} loading={evaluate.isPending}><RefreshCw /> Check results</Button>
          <Button size="sm" variant="ghost" onClick={() => cancel.mutate()} loading={cancel.isPending}>Stop</Button>
        </div>
      )}
      <Dialog open={!!choosing} onOpenChange={(o) => !o && setChoosing(null)}>
        {choosing && <DialogContent title={`Posts for variant ${choosing}`} description="Pick posts written in this variant's style. A post can only be in one variant."><ChoosePosts ws={ws} exp={exp} label={choosing} onDone={() => setChoosing(null)} /></DialogContent>}
      </Dialog>
    </article>
  );
}

export function InsightsView() {
  const { workspace } = useSession();
  const ws = workspace.id;
  const canEdit = workspace.role !== "viewer";
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const insights = useQuery({ queryKey: ["insights", ws], queryFn: () => intelligenceApi.insights(ws) });
  const experiments = useQuery({ queryKey: ["experiments", ws], queryFn: () => intelligenceApi.experiments(ws) });
  const refresh = useMutation({ mutationFn: () => intelligenceApi.refreshInsights(ws), onSuccess: () => void qc.invalidateQueries({ queryKey: ["insights", ws] }) });

  return (
    <div className="mx-auto grid max-w-5xl gap-10">
      <PageTitle
        title="Insights"
        description="What your results say, with the evidence. A finding needs at least 5 posts on each side and a clear difference; otherwise nothing is claimed."
        actions={<>
          <Button asChild variant="secondary"><Link href="/intelligence/memory">Memory</Link></Button>
          {canEdit && <Button onClick={() => refresh.mutate()} loading={refresh.isPending}><RefreshCw /> Analyse now</Button>}
        </>}
      />
      {refresh.data && <Alert tone="info" title="Analysis finished">{refresh.data.created} new, {refresh.data.updated} updated, {refresh.data.superseded} no longer supported by the data.</Alert>}
      <section className="grid gap-4">
        {insights.isPending ? <Skeleton className="h-40" /> : insights.data?.length ? (
          insights.data.map((i) => <InsightCard key={i.id} insight={i} ws={ws} canEdit={canEdit} />)
        ) : (
          <div className="grid gap-2 rounded-[var(--radius-card)] border border-dashed border-line-strong bg-surface/60 px-6 py-10">
            <h2 className="text-lg font-semibold">No findings yet</h2>
            <p className="max-w-xl text-muted">Insights appear once enough published posts have metrics to compare, for example 5 educational and 5 promotional posts. Analysis also runs every night.</p>
          </div>
        )}
      </section>

      <section className="grid gap-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="grid gap-1">
            <h2 className="flex items-center gap-2 text-xl font-semibold"><FlaskConical className="size-5 text-lab" aria-hidden /> Experiments</h2>
            <p className="text-sm text-muted">Test one thing at a time. Winners are saved to your agent&apos;s memory.</p>
          </div>
          {canEdit && <Button variant="secondary" onClick={() => setCreating(true)}><Plus /> New experiment</Button>}
        </div>
        {experiments.data?.length ? experiments.data.map((e) => <ExperimentCard key={e.id} exp={e} ws={ws} canEdit={canEdit} />) : <p className="text-sm text-muted">No experiments yet.</p>}
      </section>
      <Dialog open={creating} onOpenChange={setCreating}>
        {creating && <DialogContent title="New experiment" description="Available on Starter and above." className="w-[min(40rem,calc(100vw-2rem))]"><NewExperiment ws={ws} onDone={() => setCreating(false)} /></DialogContent>}
      </Dialog>
    </div>
  );
}
