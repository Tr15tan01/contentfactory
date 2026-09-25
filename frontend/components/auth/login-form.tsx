"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuthConfig } from "@/hooks/use-auth-config";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";
import { safeNext } from "@/lib/navigation";
import { GoogleButton } from "./google-button";
import { PasswordInput } from "./password-input";

const OAUTH_ERRORS: Record<string, string> = {
  oauth_cancelled: "Google sign-in was cancelled.",
  oauth_state_invalid: "Google sign-in expired. Try again.",
  oauth_exchange_failed: "Google didn't confirm the sign-in. Try again.",
  google_email_unverified: "Your Google email isn't verified. Verify it with Google, or sign in with email.",
  account_suspended: "This account is suspended. Contact support.",
};

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const config = useAuthConfig();
  const oauthError = params.get("error");

  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ title: string; text?: string; code?: string } | null>(
    oauthError ? { title: "Couldn't sign in with Google", text: OAUTH_ERRORS[oauthError] ?? "Try again, or sign in with email." } : null,
  );
  const [email, setEmail] = useState("");
  const [resent, setResent] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setPending(true);
    setError(null);
    try {
      await authApi.login({ email: String(data.get("email")), password: String(data.get("password")) });
      router.replace(next);
      router.refresh();
    } catch (err) {
      setPending(false);
      if (!(err instanceof ApiError)) throw err;
      if (err.code === "email_not_verified") setError({ title: "Confirm your email first", text: "We sent a confirmation link when you signed up.", code: err.code });
      else if (err.status === 429) setError({ title: "Too many attempts", text: "For your security, sign-in is paused for a few minutes. You can reset your password meanwhile." });
      else if (err.code === "invalid_credentials") setError({ title: "Email or password is incorrect" });
      else setError({ title: "Couldn't sign in", text: err.message });
    }
  }

  async function resend() {
    await authApi.resendVerification(email).catch(() => undefined);
    setResent(true);
  }

  return (
    <div className="grid gap-5">
      {config.google_enabled && <GoogleButton next={next} />}
      {error && (
        <Alert tone="error" title={error.title}>
          {error.text}
          {error.code === "email_not_verified" && (
            <>
              {" "}
              {resent ? "A new link is on its way." : (
                <button type="button" className="font-medium text-lab underline" onClick={resend}>Send a new link</button>
              )}
            </>
          )}
        </Alert>
      )}
      <form onSubmit={onSubmit} className="grid gap-5">
        <Field id="email" label="Email">
          <Input name="email" type="email" autoComplete="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field id="password" label="Password" action={<Link href="/forgot-password" className="text-sm text-lab hover:underline">Forgot password?</Link>}>
          <PasswordInput name="password" autoComplete="current-password" required />
        </Field>
        <Button type="submit" size="lg" loading={pending}>Sign in</Button>
      </form>
    </div>
  );
}
