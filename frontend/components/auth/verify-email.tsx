"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";

export function VerifyEmail() {
  const router = useRouter();
  const token = useSearchParams().get("token");
  const [state, setState] = useState<"verifying" | "failed" | "missing">(token ? "verifying" : "missing");
  const [message, setMessage] = useState<string | null>(null);
  const [resent, setResent] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return; // tokens are single-use; never submit twice (StrictMode)
    started.current = true;
    authApi
      .verifyEmail(token)
      .then(() => router.replace("/onboarding"))
      .catch((err) => {
        setState("failed");
        setMessage(err instanceof ApiError ? err.message : "We couldn't confirm your email.");
      });
  }, [token, router]);

  if (state === "verifying") {
    return (
      <p className="flex items-center gap-3 text-muted" role="status">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Confirming your email
      </p>
    );
  }

  return (
    <div className="grid gap-5">
      <Alert tone="error" title={state === "missing" ? "This link is incomplete" : "This link didn't work"}>
        {state === "missing" ? "Open the link from your email again." : message} Links last 48 hours and work once.
      </Alert>
      {resent ? (
        <Alert tone="success" title="New link sent">If that account still needs confirming, it&apos;s on its way.</Alert>
      ) : (
        <form
          className="grid gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            await authApi.resendVerification(String(new FormData(e.currentTarget).get("email")).trim()).catch(() => undefined);
            setResent(true);
          }}
        >
          <Field id="email" label="Send a new link to">
            <Input name="email" type="email" autoComplete="email" required />
          </Field>
          <Button type="submit">Send new link</Button>
        </form>
      )}
      <p className="text-sm text-muted">
        Already confirmed? <Link href="/login" className="text-lab underline">Sign in</Link>
      </p>
    </div>
  );
}
