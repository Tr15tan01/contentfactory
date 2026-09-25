import type { Metadata } from "next";
import { AppProviders } from "@/components/app/session";
import { AppShell, ShellSkeleton } from "@/components/app/app-shell";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppProviders fallback={<ShellSkeleton />}>
      <AppShell>{children}</AppShell>
    </AppProviders>
  );
}
