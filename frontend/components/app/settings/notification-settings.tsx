"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/components/app/session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { activityApi } from "@/lib/api/endpoints";
import type { NotificationPreference } from "@/types/api";
import { SettingsSection } from "./section";

export function NotificationSettings() {
  const { workspace, user } = useSession();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["notification-prefs", workspace.id], queryFn: () => activityApi.preferences(workspace.id) });
  const [draft, setDraft] = useState<NotificationPreference[] | null>(null);
  const rows = draft ?? q.data ?? [];
  const save = useMutation({
    mutationFn: () => activityApi.savePreferences(workspace.id, rows.map(({ type, in_app, email }) => ({ type, in_app, email }))),
    onSuccess: (data) => { qc.setQueryData(["notification-prefs", workspace.id], data); setDraft(null); },
  });
  const set = (type: string, key: "in_app" | "email", value: boolean) => setDraft(rows.map((r) => (r.type === type ? { ...r, [key]: value } : r)));

  return (
    <div className="grid gap-10">
      <SettingsSection title="Notifications" description={`For ${workspace.name}. Emails go to ${user.email}. Reminder times are set in Business, Media and publishing.`}>
        {q.isPending ? <Skeleton className="h-64" /> : (
          <div className="grid gap-4">
            {save.isSuccess && !draft && <Alert tone="success" title="Saved" />}
            <table className="w-full text-left text-sm">
              <thead className="text-muted"><tr><th scope="col" className="pb-2 font-medium">Tell me about</th><th scope="col" className="w-20 pb-2 text-center font-medium">In app</th><th scope="col" className="w-20 pb-2 text-center font-medium">Email</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.type} className="border-t border-line">
                    <th scope="row" className="py-3 font-normal">{r.label}</th>
                    <td className="text-center"><input type="checkbox" className="size-4 accent-[var(--lab)]" checked={r.in_app} onChange={(e) => set(r.type, "in_app", e.target.checked)} aria-label={`${r.label} in app`} /></td>
                    <td className="text-center"><input type="checkbox" className="size-4 accent-[var(--lab)]" checked={r.email} onChange={(e) => set(r.type, "email", e.target.checked)} aria-label={`${r.label} by email`} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center gap-3">
              <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!draft}>Save</Button>
              <Link href="/settings/business" className="text-sm text-lab underline">Change reminder times</Link>
            </div>
          </div>
        )}
      </SettingsSection>
    </div>
  );
}
