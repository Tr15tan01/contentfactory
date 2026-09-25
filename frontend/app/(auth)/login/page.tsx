import { Suspense } from "react";
import Link from "next/link";
import { AuthShell } from "@/components/auth/auth-shell";
import { LoginForm } from "@/components/auth/login-form";

export const metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <AuthShell title="Welcome back" footer={<>New to ContentFactory? <Link href="/register" className="font-medium text-lab hover:underline">Create an account</Link></>}>
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
