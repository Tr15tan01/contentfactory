"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Laptop, Smartphone } from "lucide-react";
import { PasswordInput } from "@/components/auth/password-input";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuthConfig } from "@/hooks/use-auth-config";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";
import type { SessionInfo } from "@/types/api";
import { useSession } from "../session";
import { SettingsSection } from "./section";

function describeDevice(ua: string | null): { label: string; mobile: boolean } {
  if (!ua) return { label: "Unknown device", mobile: false };
  const mobile = /Mobile|Android|iPhone|iPad/i.test(ua);
  const browser = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : "Browser";
  const os = /Windows/.test(ua) ? "Windows" : /Mac OS X/.test(ua) && !mobile ? "macOS" : /iPhone|iPad/.test(ua) ? "iOS" : /Android/.test(ua) ? "Android" : /Linux/.test(ua) ? "Linux" : "";
  return { label: os ? `${browser} on ${os}` : browser, mobile };
}

function PasswordSection() {
  const { user } = useSession();
  const config = useAuthConfig();
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const change = useMutation({
    mutationFn: (body: { current_password?: string; new_password: string }) => authApi.changePassword(body),
  });

  return (
    <SettingsSection
      title={user.has_password ? "Password" : "Set a password"}
      description={user.has_password ? "Changing it signs you out on your other devices." : "You sign in with Google. Add a password to also sign in with email."}
    >
      <form
        className="grid gap-5"
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const data = new FormData(form);
          const next = String(data.get("new_password"));
          if (next !== String(data.get("confirm"))) {
            setFieldErrors({ confirm: "The two passwords don't match." });
            return;
          }
          setError(null);
          setFieldErrors({});
          change.mutate(
            { current_password: user.has_password ? String(data.get("current_password")) : undefined, new_password: next },
            {
              onSuccess: () => form.reset(),
              onError: (err) => {
                if (err instanceof ApiError && err.code === "invalid_current_password") setFieldErrors({ current_password: err.message });
                else if (err instanceof ApiError && err.code === "weak_password") setFieldErrors({ new_password: err.message });
                else setError(err instanceof ApiError ? err.message : "Password not changed. Try again.");
              },
            },
          );
        }}
      >
        {error && <Alert tone="error" title="Password not changed">{error}</Alert>}
        {change.isSuccess && <Alert tone="success" title="Password changed">Other devices have been signed out.</Alert>}
        {user.has_password && (
          <Field id="current_password" label="Current password" error={fieldErrors.current_password}>
            <PasswordInput name="current_password" autoComplete="current-password" required />
          </Field>
        )}
        <Field id="new_password" label="New password" hint={`At least ${config.password_min_length} characters.`} error={fieldErrors.new_password}>
          <PasswordInput name="new_password" autoComplete="new-password" required minLength={config.password_min_length} />
        </Field>
        <Field id="confirm" label="Repeat new password" error={fieldErrors.confirm}>
          <PasswordInput name="confirm" autoComplete="new-password" required />
        </Field>
        <div>
          <Button type="submit" loading={change.isPending}>{user.has_password ? "Change password" : "Set password"}</Button>
        </div>
      </form>
    </SettingsSection>
  );
}

function SessionRow({ session, onRevoke, busy }: { session: SessionInfo; onRevoke: () => void; busy: boolean }) {
  const device = describeDevice(session.user_agent);
  const Icon = device.mobile ? Smartphone : Laptop;
  const last = new Date(session.last_used_at).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
  return (
    <li className="flex items-center gap-4 py-3.5">
      <Icon className="size-5 shrink-0 text-muted" aria-hidden />
      <div className="grid min-w-0 flex-1">
        <p className="truncate font-medium">
          {device.label}
          {session.current && <span className="ml-2 rounded-full bg-lab-soft px-2 py-0.5 text-xs font-medium text-lab">This device</span>}
        </p>
        <p className="truncate text-sm text-muted">
          {session.ip_address ?? "Unknown location"}, last active {last}
          {session.auth_method === "google" ? ", signed in with Google" : ""}
        </p>
      </div>
      {!session.current && (
        <Button variant="secondary" size="sm" onClick={onRevoke} loading={busy}>Sign out</Button>
      )}
    </li>
  );
}

function SessionsSection() {
  const queryClient = useQueryClient();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: authApi.sessions });
  const revoke = useMutation({
    mutationFn: authApi.revokeSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
  const revokeOthers = useMutation({
    mutationFn: authApi.revokeOtherSessions,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
  const others = sessions.data?.filter((s) => !s.current).length ?? 0;

  return (
    <SettingsSection title="Where you're signed in" description="Sign out any device you don't recognise, then change your password.">
      <div className="grid gap-4">
        {sessions.isPending ? (
          <div className="grid gap-3"><Skeleton className="h-12" /><Skeleton className="h-12" /></div>
        ) : sessions.error ? (
          <Alert tone="error" title="Sessions didn't load">{sessions.error instanceof ApiError ? sessions.error.message : "Try again."}</Alert>
        ) : (
          <ul className="divide-y divide-line border-y border-line">
            {sessions.data.map((s) => (
              <SessionRow key={s.id} session={s} busy={revoke.isPending && revoke.variables === s.id} onRevoke={() => revoke.mutate(s.id)} />
            ))}
          </ul>
        )}
        {others > 0 && (
          <div>
            <Button variant="secondary" onClick={() => revokeOthers.mutate()} loading={revokeOthers.isPending}>
              Sign out {others} other {others === 1 ? "device" : "devices"}
            </Button>
          </div>
        )}
      </div>
    </SettingsSection>
  );
}

function DeleteAccountSection() {
  const { user } = useSession();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const remove = useMutation({ mutationFn: authApi.deleteAccount });

  return (
    <SettingsSection title="Delete account" description="Permanently deletes your account and the workspaces you own, including their content, media and memory.">
      <Dialog onOpenChange={() => setError(null)}>
        <DialogTrigger asChild>
          <Button variant="danger">Delete account</Button>
        </DialogTrigger>
        <DialogContent title="Delete your account?" description="This can't be undone. Scheduled posts in workspaces you own will not publish.">
          <form
            className="mt-5 grid gap-5"
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              const body = user.has_password
                ? { password: String(data.get("password")) }
                : { confirm_email: String(data.get("confirm_email")).trim() };
              remove.mutate(body, {
                onSuccess: () => {
                  queryClient.clear();
                  router.replace("/?account=deleted");
                },
                onError: (err) => setError(err instanceof ApiError ? err.message : "Account not deleted. Try again."),
              });
            }}
          >
            {error && <Alert tone="error" title="Account not deleted">{error}</Alert>}
            {user.has_password ? (
              <Field id="delete_password" label="Enter your password to confirm">
                <PasswordInput name="password" autoComplete="current-password" required />
              </Field>
            ) : (
              <Field id="confirm_email" label={`Type ${user.email} to confirm`}>
                <Input name="confirm_email" type="email" required autoComplete="off" />
              </Field>
            )}
            <div className="flex justify-end gap-2">
              <DialogClose asChild><Button variant="secondary" type="button">Keep my account</Button></DialogClose>
              <Button variant="danger" type="submit" loading={remove.isPending}>Delete permanently</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </SettingsSection>
  );
}

export function SecuritySettings() {
  return (
    <div className="grid gap-10">
      <PasswordSection />
      <SessionsSection />
      <DeleteAccountSection />
    </div>
  );
}
