"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { activityApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

function ago(iso: string): string {
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h} h ago` : `${Math.round(h / 24)} d ago`;
}

export function NotificationBell() {
  const router = useRouter();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["notifications"], queryFn: activityApi.notifications, refetchInterval: 60_000 });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["notifications"] });
  const read = useMutation({ mutationFn: activityApi.read, onSuccess: refresh });
  const readAll = useMutation({ mutationFn: activityApi.readAll, onSuccess: refresh });
  const unread = q.data?.unread ?? 0;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="relative grid size-9 place-items-center rounded-full text-muted outline-none hover:bg-sunk hover:text-ink focus-visible:ring-2 focus-visible:ring-lab" aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}>
        <Bell className="size-5" aria-hidden />
        {unread > 0 && <span className="numeric absolute -right-0.5 -top-0.5 grid min-w-5 place-items-center rounded-full bg-signal px-1 text-[0.6875rem] font-semibold text-white">{unread > 9 ? "9+" : unread}</span>}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[min(24rem,calc(100vw-2rem))] p-0">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <p className="text-sm font-semibold">Notifications</p>
          {unread > 0 && <button className="text-xs text-lab hover:underline" onClick={(e) => { e.preventDefault(); readAll.mutate(); }}>Mark all read</button>}
        </div>
        <div className="max-h-[60vh] overflow-y-auto p-1.5">
          {q.data?.items.length ? q.data.items.map((n) => (
            <DropdownMenuItem key={n.id} className="grid items-start gap-0.5 py-2.5" onSelect={() => { if (!n.read_at) read.mutate(n.id); if (n.action_url) router.push(n.action_url); }}>
              <span className="flex items-start gap-2">
                {!n.read_at && <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", n.priority === "high" ? "bg-signal" : "bg-lab")} aria-label="Unread" />}
                <span className={cn("text-sm leading-snug", !n.read_at && "font-medium")}>{n.title}</span>
              </span>
              {n.body && <span className="line-clamp-2 text-xs text-muted">{n.body}</span>}
              <span className="text-xs text-faint">{n.workspace_name}, {ago(n.created_at)}</span>
            </DropdownMenuItem>
          )) : <p className="px-3 py-6 text-center text-sm text-muted">You&apos;re all caught up.</p>}
        </div>
        <DropdownMenuSeparator className="my-0" />
        <DropdownMenuItem onSelect={() => router.push("/settings/notifications")} className="justify-center text-xs text-muted">Notification settings</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
