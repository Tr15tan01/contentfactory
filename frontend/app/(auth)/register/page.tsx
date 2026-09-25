import Link from "next/link";
import { AuthShell } from "@/components/auth/auth-shell";
import { RegisterForm } from "@/components/auth/register-form";

export const metadata = { title: "Create your account" };

export default function RegisterPage() {
  return (
    <AuthShell
      title="Start free"
      subtitle="Free plan, no card needed. You can upgrade any time."
      footer={<>Already have an account? <Link href="/login" className="font-medium text-lab hover:underline">Sign in</Link></>}
    >
      <RegisterForm />
    </AuthShell>
  );
}
