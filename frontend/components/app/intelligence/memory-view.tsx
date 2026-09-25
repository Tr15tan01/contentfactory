"use client";

import { useDeferredValue, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Pin, PinOff, Plus, Search, Trash2 } from "lucide-react";
import { PageTitle } from "@/components/app/page-title";
import { useSession } from "@/components/app/session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { intelligenceApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";
import type { Memory, MemoryCategory } from "@/types/api";

export const CATEGORY_LABELS: Record<MemoryCategory, string> = {
  audience: "Audience", brand: "Brand", successful_topic: "Topics that work", weak_topic: "Topics that don't",
  successful_format: "Formats that work", weak_format: "Formats that don't", successful_hook: "Hooks that work",
  successful_cta: "Calls to action that work", platform_pattern: "Platform patterns", posting_time: "Posting times",
  experiment: "Experiment results", customer_feedback: "Customer feedback",
};
const SOURCE: Record<Memory["source"], string> = { user: "Added by you", analytics: "From your results", experiment: "From an experiment", agent: "From your agent" };

function Row({ m, ws, canEdit }: { m: Memory; ws: string; canEdit: boolean }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(m.content);
  const done = () => { setEditing(false); void qc.invalidateQueries({ queryKey: ["memory", ws] }); };
  const edit = useMutation({ mutationFn: (body: Partial<{ content: string; pinned: boolean }>) => intelligenceApi.editMemory(ws, m.id, body), onSuccess: done });
  const remove = useMutation({ mutationFn: () => intelligenceApi.deleteMemory(ws, m.id), onSuccess: done });
  return (
    <li className="grid gap-2 py-4">
      {editing ? (
        <form className="grid gap-2" onSubmit={(e) => { e.preventDefault(); edit.mutate({ content: text }); }}>
          <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} className="min-h-16" maxLength={1000} autoFocus />
          <div className="flex gap-2"><Button size="sm" type="submit" loading={edit.isPending}>Save</Button><Button size="sm" variant="ghost" type="button" onClick={() => { setEditing(false); setText(m.content); }}>Cancel</Button></div>
        </form>
      ) : (
        <p className={cn("leading-snug", m.pinned && "font-medium")}>{m.content}</p>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <span>{CATEGORY_LABELS[m.category]}</span>
        <span>{SOURCE[m.source]}</span>
        {m.pinned && <span className="text-lab">Always used</span>}
        {m.last_used_at && <span>Last used {new Date(m.last_used_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>}
        {canEdit && !editing && (
          <span className="ml-auto flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => edit.mutate({ pinned: !m.pinned })}>{m.pinned ? <PinOff aria-hidden /> : <Pin aria-hidden />}{m.pinned ? "Unpin" : "Always use"}</Button>
            <Button size="icon" variant="ghost" onClick={() => setEditing(true)} aria-label="Edit"><Pencil className="size-4" /></Button>
            <Button size="icon" variant="ghost" onClick={() => remove.mutate()} aria-label="Delete"><Trash2 className="size-4" /></Button>
          </span>
        )}
      </div>
    </li>
  );
}

export function MemoryView() {
  const { workspace } = useSession();
  const ws = workspace.id;
  const canEdit = workspace.role !== "viewer";
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<MemoryCategory | "">("");
  const q = useDeferredValue(search.trim());
  const [draft, setDraft] = useState({ content: "", category: "audience" as MemoryCategory, pinned: false });
  const list = useQuery({ queryKey: ["memory", ws, q, category], queryFn: () => intelligenceApi.memory(ws, q || undefined, category || undefined) });
  const add = useMutation({
    mutationFn: () => intelligenceApi.addMemory(ws, draft),
    onSuccess: () => { setDraft({ ...draft, content: "" }); void qc.invalidateQueries({ queryKey: ["memory", ws] }); },
  });

  return (
    <div className="mx-auto grid max-w-4xl gap-8">
      <PageTitle
        title="Marketing memory"
        description="What your agent knows from your results and from you. The most relevant items are included whenever it drafts a post; pinned ones always are. Nothing here trains an AI model."
        actions={<Button asChild variant="secondary"><Link href="/insights">Insights</Link></Button>}
      />
      {canEdit && (
        <form className="grid gap-4 rounded-[var(--radius-card)] bg-surface p-5 ring-1 ring-line" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
          {add.error && <Alert tone="error" title="Not saved">{add.error instanceof ApiError ? add.error.message : "Try again."}</Alert>}
          <Field id="mem-content" label="Teach your agent something" hint="A fact, a rule or a preference, in one or two sentences.">
            <Textarea value={draft.content} onChange={(e) => setDraft({ ...draft, content: e.target.value })} rows={2} className="min-h-16" maxLength={1000} placeholder="Our regulars are mostly students from the nearby university." />
          </Field>
          <div className="flex flex-wrap items-end gap-3">
            <Field id="mem-cat" label="Type" className="w-60">
              <Select value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value as MemoryCategory })}>
                {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            </Field>
            <label className="flex h-11 items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--lab)]" checked={draft.pinned} onChange={(e) => setDraft({ ...draft, pinned: e.target.checked })} /> Always use</label>
            <Button type="submit" className="ml-auto" loading={add.isPending} disabled={draft.content.trim().length < 3}><Plus /> Add</Button>
          </div>
        </form>
      )}
      <div className="flex flex-wrap gap-3">
        <label className="relative min-w-56 flex-1">
          <span className="sr-only">Search memory</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" aria-hidden />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search, e.g. oat milk or evenings" className="pl-9" />
        </label>
        <Select value={category} onChange={(e) => setCategory(e.target.value as MemoryCategory | "")} className="w-56" aria-label="Type">
          <option value="">All types</option>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      </div>
      {list.isPending ? <Skeleton className="h-40" /> : list.data?.length ? (
        <ul className="divide-y divide-line border-y border-line">{list.data.map((m) => <Row key={m.id} m={m} ws={ws} canEdit={canEdit} />)}</ul>
      ) : (
        <p className="text-muted">{q || category ? "Nothing matches." : "Nothing yet. Save findings from Insights, or add what you know about your customers."}</p>
      )}
    </div>
  );
}
