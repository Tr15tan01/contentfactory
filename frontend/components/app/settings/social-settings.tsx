"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Link2, Unlink } from "lucide-react";
import { useSession } from "@/components/app/session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Meter } from "@/components/ui/meter";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { socialApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";
import type { SocialAccount } from "@/types/api";
import { PLATFORM_RULES } from "../content/meta";
import { PageTitle } from "../page-title";

const NOTES: Record<string, string> = {
  meta: "Connect Instagram professional (business or creator) accounts through the Facebook Page they're linked to. Your Pages are connected too.",
  tiktok: "Publishes videos. Until TikTok reviews this app, TikTok only allows posts visible to you (private).",
  youtube: "Publishes Shorts and videos to your channel. Until Google verifies this app, uploads stay private.",
};

function Result() {
  const params = useSearchParams();
  if (params.get("error")) {
    return <Alert tone="error" title="Not connected">{params.get("message") ?? "The connection didn't complete. Try again."}</Alert>;
  }
  if (params.get("connected") !== null) {
    const connected = Number(params.get("connected")), reconnected = Number(params.get("reconnected")), skipped = Number(params.get("skipped"));
    const parts = [
      connected && `${connected} account${connected === 1 ? "" : "s"} connected`,
      reconnected && `${reconnected} reconnected`,
    ].filter(Boolean);
    return (
      <Alert tone={skipped ? "info" : "success"} title={parts.join(", ") || "Nothing new to connect"}>
        {skipped ? `${skipped} more ${skipped === 1 ? "account was" : "accounts were"} found but not connected: your plan's account limit is reached. Disconnect one or upgrade to add them.` : null}
      </Alert>
    );
  }
  return null;
}

function AccountRow({ account, canManage, onDisconnect }: { account: SocialAccount; canManage: boolean; onDisconnect: () => void }) {
  const expired = account.status !== "connected";
  return (
    <li className="flex items-center gap-3 py-3">
      {/* eslint-disable-next-line @next/next/no-img-element -- avatar URL from the platform */}
      {account.avatar_url ? <img src={account.avatar_url} alt="" className="size-9 rounded-full object-cover" referrerPolicy="no-referrer" /> : <span className="grid size-9 place-items-center rounded-full bg-sunk text-xs font-semibold">{(account.display_name ?? "?").slice(0, 2).toUpperCase()}</span>}
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{account.display_name ?? account.username ?? "Account"}</p>
        <p className="truncate text-sm text-muted">
          {PLATFORM_RULES[account.platform].label}{account.username ? `, @${account.username}` : ""}
        </p>
        {expired && <p className="mt-1 flex items-center gap-1.5 text-sm text-signal"><AlertTriangle className="size-3.5" aria-hidden /> {account.last_error ?? "Needs reconnecting."}</p>}
      </div>
      <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", expired ? "bg-signal-soft text-signal" : "bg-lab-soft text-lab")}>{expired ? "Reconnect" : "Connected"}</span>
      {canManage && <Button variant="ghost" size="icon" onClick={onDisconnect} aria-label={`Disconnect ${account.display_name ?? "account"}`}><Unlink className="size-4" /></Button>}
    </li>
  );
}

export function SocialSettings() {
  const { workspace } = useSession();
  const ws = workspace.id;
  const canManage = workspace.role === "owner" || workspace.role === "admin";
  const queryClient = useQueryClient();
  const [removing, setRemoving] = useState<SocialAccount | null>(null);
  const [error, setError] = useState<string | null>(null);
  const social = useQuery({ queryKey: ["social", ws], queryFn: () => socialApi.get(ws) });
  const connect = useMutation({
    mutationFn: (provider: string) => socialApi.connect(ws, provider),
    onSuccess: ({ authorize_url }) => window.location.assign(authorize_url),
    onError: (e) => setError(e instanceof ApiError ? e.message : "Couldn't start the connection."),
  });
  const disconnect = useMutation({
    mutationFn: (id: string) => socialApi.disconnect(ws, id),
    onSuccess: () => { setRemoving(null); void queryClient.invalidateQueries({ queryKey: ["social", ws] }); },
  });

  return (
    <div className="grid gap-8">
      <PageTitle title="Social accounts" description="Connect the accounts your agent publishes to. Each uses the platform's official sign-in; we never see your passwords." />
      <Result />
      {error && <Alert tone="error" title="Not connected">{error}</Alert>}
      {social.isPending ? (
        <Skeleton className="h-64" />
      ) : !social.data ? (
        <Alert tone="error" title="Accounts didn't load">Try again.</Alert>
      ) : (
        <>
          {social.data.publishing_needs_public_media && (
            <Alert tone="info" title="Publishing needs public media storage">
              This server keeps files on local disk, which social platforms can&apos;t fetch. Accounts can be connected, but posts with photos or videos will fail until S3-compatible storage is configured.
            </Alert>
          )}
          <div className="max-w-sm"><Meter label="Connected accounts" used={social.data.limit.used} limit={social.data.limit.limit} /></div>
          <div className="grid gap-4 lg:grid-cols-3">
            {social.data.providers.map((p) => {
              const accounts = social.data.accounts.filter((a) => p.platforms.includes(a.platform));
              return (
                <section key={p.provider} className="grid content-start gap-4 rounded-[var(--radius-card)] bg-surface p-5 ring-1 ring-line">
                  <div className="grid gap-1">
                    <h2 className="text-lg font-semibold">{p.label}</h2>
                    <p className="text-sm text-muted">{NOTES[p.provider]}</p>
                  </div>
                  {accounts.length > 0 && (
                    <ul className="divide-y divide-line border-y border-line">
                      {accounts.map((a) => <AccountRow key={a.id} account={a} canManage={canManage} onDisconnect={() => setRemoving(a)} />)}
                    </ul>
                  )}
                  {!p.configured ? (
                    <p className="rounded-md bg-sunk px-3 py-2 text-sm text-muted">Not available on this server yet: the {p.label} app credentials aren&apos;t configured.</p>
                  ) : canManage ? (
                    <Button variant={accounts.length ? "secondary" : "primary"} className="justify-self-start" onClick={() => connect.mutate(p.provider)} loading={connect.isPending && connect.variables === p.provider}>
                      <Link2 /> {accounts.length ? "Connect or reconnect" : `Connect ${p.label}`}
                    </Button>
                  ) : (
                    <p className="text-sm text-muted">Only owners and admins can connect accounts.</p>
                  )}
                </section>
              );
            })}
          </div>
        </>
      )}
      <Dialog open={!!removing} onOpenChange={(o) => !o && setRemoving(null)}>
        {removing && (
          <DialogContent title={`Disconnect ${removing.display_name ?? "this account"}?`} description="Its access tokens are deleted. Scheduled posts for it won't publish until you connect an account again.">
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setRemoving(null)}>Keep connected</Button>
              <Button variant="danger" onClick={() => disconnect.mutate(removing.id)} loading={disconnect.isPending}>Disconnect</Button>
            </div>
          </DialogContent>
        )}
      </Dialog>
    </div>
  );
}
