"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuthConfig } from "@/hooks/use-auth-config";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";
import { PasswordInput } from "./password-input";

export function ForgotPasswordForm() {
  const [pending, setPending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      await authApi.forgotPassword(String(new FormData(e.currentTarget).get("email")).trim());
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 429 ? "Too many requests. Try again in an hour." : "Couldn't send the link. Try again.");
    } finally {
      setPending(false);
    }
  }

  if (sent) {
    return (
      <Alert tone="success" title="Check your inbox">
        If an account exists for that email, a reset link is on its way. It expires in 30 minutes.
      </Alert>
    );
  }
  return (
    <form onSubmit={onSubmit} className="grid gap-5">
      {error && <Alert tone="error" title="Link not sent">{error}</Alert>}
      <Field id="email" label="Email">
        <Input name="email" type="email" autoComplete="email" required autoFocus />
      </Field>
      <Button type="submit" size="lg" loading={pending}>Send reset link</Button>
    </form>
  );
}

export function ResetPasswordForm() {
  const token = useSearchParams().get("token") ?? "";
  const config = useAuthConfig();
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);

  if (!token) {
    return (
      <Alert tone="error" title="This reset link is incomplete">
        Open the link from your email again, or <Link href="/forgot-password">request a new one</Link>.
      </Alert>
    );
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const password = String(data.get("password"));
    if (password !== String(data.get("confirm"))) {
      setFieldError("The two passwords don't match.");
      return;
    }
    setPending(true);
    setError(null);
    setFieldError(null);
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError && err.code === "weak_password") setFieldError(err.message);
      else if (err instanceof ApiError && err.code === "invalid_token") setError("expired");
      else setError(err instanceof ApiError ? err.message : "Couldn't reset your password. Try again.");
    } finally {
      setPending(false);
    }
  }

  if (done) {
    return (
      <div className="grid gap-5">
        <Alert tone="success" title="Password changed">
          For your security, you&apos;ve been signed out on every device.
        </Alert>
        <Button asChild size="lg"><Link href="/login">Sign in</Link></Button>
      </div>
    );
  }
  return (
    <form onSubmit={onSubmit} className="grid gap-5">
      {error === "expired" ? (
        <Alert tone="error" title="This link has expired or was already used">
          <Link href="/forgot-password">Request a new link</Link>. Links work once and last 30 minutes.
        </Alert>
      ) : error ? (
        <Alert tone="error" title="Password not changed">{error}</Alert>
      ) : null}
      <Field id="password" label="New password" hint={`At least ${config.password_min_length} characters.`} error={fieldError}>
        <PasswordInput name="password" autoComplete="new-password" required minLength={config.password_min_length} autoFocus />
      </Field>
      <Field id="confirm" label="Repeat new password">
        <PasswordInput name="confirm" autoComplete="new-password" required />
      </Field>
      <Button type="submit" size="lg" loading={pending}>Change password</Button>
    </form>
  );
}
