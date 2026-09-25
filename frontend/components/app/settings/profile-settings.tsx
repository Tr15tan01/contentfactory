"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { authApi, workspaceApi } from "@/lib/api/endpoints";
import { useSession } from "../session";
import { SettingsSection } from "./section";
import { TimezoneSelect } from "./timezone-select";

function errorText(err: unknown): string {
  if (!(err instanceof ApiError)) return "Try again.";
  return Object.values(err.fields)[0] ?? err.message;
}

function Saved({ show }: { show: boolean }) {
  return show ? <span role="status" className="text-sm text-lab">Saved</span> : null;
}

export function ProfileSettings() {
  const { user, workspace } = useSession();
  const queryClient = useQueryClient();
  const canEditWorkspace = workspace.role === "owner" || workspace.role === "admin";

  const [fullName, setFullName] = useState(user.full_name ?? "");
  const [timezone, setTimezone] = useState(user.timezone);
  const [wsName, setWsName] = useState(workspace.name);
  const [wsTimezone, setWsTimezone] = useState(workspace.timezone);

  const profile = useMutation({
    mutationFn: () => authApi.updateMe({ full_name: fullName.trim() || null, timezone }),
    onSuccess: (u) => queryClient.setQueryData(["me"], u),
  });
  const ws = useMutation({
    mutationFn: () => workspaceApi.update(workspace.id, { name: wsName.trim(), timezone: wsTimezone }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard", workspace.id] });
    },
  });

  return (
    <div className="grid gap-10">
      <SettingsSection title="Your profile" description="How you appear to teammates, and the time zone used for your greetings and reminders.">
        <form className="grid gap-5" onSubmit={(e) => { e.preventDefault(); profile.mutate(); }}>
          {profile.error && <Alert tone="error" title="Profile not saved">{errorText(profile.error)}</Alert>}
          <Field id="full_name" label="Name">
            <Input value={fullName} onChange={(e) => { setFullName(e.target.value); profile.reset(); }} maxLength={120} autoComplete="name" />
          </Field>
          <Field id="email" label="Email" hint={user.email_verified ? "Confirmed" : "Not confirmed yet"}>
            <Input value={user.email} readOnly disabled />
          </Field>
          <Field id="timezone" label="Your time zone">
            <TimezoneSelect value={timezone} onChange={(e) => { setTimezone(e.target.value); profile.reset(); }} />
          </Field>
          <div className="flex items-center gap-4">
            <Button type="submit" loading={profile.isPending}>Save profile</Button>
            <Saved show={profile.isSuccess} />
          </div>
        </form>
      </SettingsSection>

      <SettingsSection
        title="Workspace"
        description={canEditWorkspace ? "The business this workspace belongs to. Its time zone is used for scheduling." : "Only owners and admins can change workspace settings."}
      >
        <form className="grid gap-5" onSubmit={(e) => { e.preventDefault(); ws.mutate(); }}>
          {ws.error && <Alert tone="error" title="Workspace not saved">{errorText(ws.error)}</Alert>}
          <Field id="ws_name" label="Business name">
            <Input value={wsName} onChange={(e) => { setWsName(e.target.value); ws.reset(); }} required maxLength={120} disabled={!canEditWorkspace} />
          </Field>
          <Field id="ws_timezone" label="Scheduling time zone" hint="Posts are scheduled and reported in this time zone.">
            <TimezoneSelect value={wsTimezone} onChange={(e) => { setWsTimezone(e.target.value); ws.reset(); }} disabled={!canEditWorkspace} />
          </Field>
          {canEditWorkspace && (
            <div className="flex items-center gap-4">
              <Button type="submit" loading={ws.isPending}>Save workspace</Button>
              <Saved show={ws.isSuccess} />
            </div>
          )}
        </form>
      </SettingsSection>
    </div>
  );
}
