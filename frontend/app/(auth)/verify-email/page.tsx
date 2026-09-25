import { Suspense } from "react";
import { AuthShell } from "@/components/auth/auth-shell";
import { VerifyEmail } from "@/components/auth/verify-email";

export const metadata = { title: "Confirm your email" };

export default function VerifyEmailPage() {
  return (
    <AuthShell title="Confirm your email">
      <Suspense>
        <VerifyEmail />
      </Suspense>
    </AuthShell>
  );
}
