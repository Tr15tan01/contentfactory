"use client";

import { useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { Meter } from "@/components/ui/meter";
import { contentApi } from "@/lib/api/endpoints";

export function useUsage(ws: string) {
  return useQuery({ queryKey: ["usage", ws], queryFn: () => contentApi.usage(ws) });
}

export function UsageNote({ ws }: { ws: string }) {
  const usage = useUsage(ws);
  if (!usage.data) return null;
  const u = usage.data;
  const resets = new Date(u.period_end).toLocaleDateString("en-US", { month: "long", day: "numeric" });
  return (
    <div className="grid gap-3 rounded-[var(--radius-card)] bg-surface p-4 ring-1 ring-line">
      <Meter used={u.ai_content.used} limit={u.ai_content.limit} label="AI drafts this month" />
      <p className="text-xs text-muted">
        {u.ai_content.remaining} left, resets {resets}. A failed draft doesn&apos;t count, and repeating an identical request is free.
      </p>
      {u.ai_provider === "mock" && (
        <p className="flex gap-2 rounded-md bg-marker-soft px-3 py-2 text-xs text-ink dark:text-marker">
          <FlaskConical className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          Development mode: drafts come from the offline test writer, not a real AI model. Set AI_PROVIDER to connect one.
        </p>
      )}
    </div>
  );
}
