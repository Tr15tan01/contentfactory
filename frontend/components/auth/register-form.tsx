"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MailCheck } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuthConfig } from "@/hooks/use-auth-config";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";
import { GoogleButton } from "./google-button";
import { PasswordInput } from "./password-input";

export function RegisterForm() {
  const router = useRouter();
  const config = useAuthConfig();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [resent, setResent] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const email = String(data.get("email")).trim();
    const password = String(data.get("password"));
    if (password.length < config.password_min_length) {
      setFieldErrors({ password: `Use at least ${config.password_min_length} characters.` });
      return;
    }
    setPending(true);
    setError(null);
    setFieldErrors({});
    try {
      const result = await authApi.register({ email, password, full_name: String(data.get("full_name")).trim() || undefined });
      if (result.verification_required) {
        setSentTo(email);
        setPending(false);
      } else {
        router.replace("/onboarding");
      }
    } catch (err) {
      setPending(false);
      if (!(err instanceof ApiError)) throw err;
      if (Object.keys(err.fields).length) setFieldErrors(err.fields);
      else if (err.code === "email_taken") setFieldErrors({ email: "An account with this email already exists. Sign in instead." });
      else if (err.status === 429) setError("Too many sign-ups from this network. Try again later.");
      else setError(err.message);
    }
  }

  if (sentTo) {
    return (
      <div className="grid gap-5">
        <div className="flex gap-4 rounded-[var(--radius-card)] bg-surface p-5 ring-1 ring-line">
          <MailCheck className="mt-0.5 size-6 shrink-0 text-lab" aria-hidden />
          <div className="grid gap-1.5">
            <p className="font-semibold">Check your inbox</p>
            <p className="text-sm text-muted">
              We sent a confirmation link to <strong className="text-ink">{sentTo}</strong>. It expires in 48 hours.
            </p>
          </div>
        </div>
        <p className="text-sm text-muted">
          Nothing arrived after a few minutes? Check spam, or{" "}
          {resent ? (
            <span>we&apos;ve sent another link.</span>
          ) : (
            <button
              type="button"
              className="font-medium text-lab underline"
              onClick={async () => {
                await authApi.resendVerification(sentTo).catch(() => undefined);
                setResent(true);
              }}
            >
              send a new link
            </button>
          )}
          .
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-5">
      {config.google_enabled && <GoogleButton label="Sign up with Google" />}
      {error && <Alert tone="error" title="Couldn't create your account">{error}</Alert>}
      <form onSubmit={onSubmit} className="grid gap-5">
        <Field id="full_name" label="Your name">
          <Input name="full_name" autoComplete="name" maxLength={120} />
        </Field>
        <Field id="email" label="Work email" error={fieldErrors.email}>
          <Input name="email" type="email" autoComplete="email" required />
        </Field>
        <Field id="password" label="Password" error={fieldErrors.password} hint={`At least ${config.password_min_length} characters. A short phrase works well.`}>
          <PasswordInput name="password" autoComplete="new-password" required minLength={config.password_min_length} />
        </Field>
        <Button type="submit" size="lg" loading={pending}>Create account</Button>
        <p className="text-xs text-muted">
          By creating an account you agree to the <Link href="/terms" className="underline">Terms</Link> and{" "}
          <Link href="/privacy" className="underline">Privacy Policy</Link>.
        </p>
      </form>
    </div>
  );
}
