import Link from "next/link";
import { AuthShell } from "@/components/auth/auth-shell";
import { ForgotPasswordForm } from "@/components/auth/password-reset-forms";

export const metadata = { title: "Reset your password" };

export default function ForgotPasswordPage() {
  return (
    <AuthShell title="Reset your password" subtitle="Enter your email and we'll send you a link to choose a new one." footer={<Link href="/login" className="text-lab hover:underline">Back to sign in</Link>}>
      <ForgotPasswordForm />
    </AuthShell>
  );
}
