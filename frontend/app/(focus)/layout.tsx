import type { Metadata } from "next";
import { AppProviders } from "@/components/app/session";
import { ShellSkeleton } from "@/components/app/app-shell";

export const metadata: Metadata = { robots: { index: false, follow: false } };

/** Signed-in pages without the sidebar (guided setup). */
export default function FocusLayout({ children }: { children: React.ReactNode }) {
  return <AppProviders fallback={<ShellSkeleton />}>{children}</AppProviders>;
}
