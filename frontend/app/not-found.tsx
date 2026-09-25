import Link from "next/link";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main id="main" className="grid min-h-dvh place-items-center px-6 py-16">
      <div className="grid max-w-md gap-6">
        <Logo />
        <h1 className="display-tight text-5xl">This page doesn&apos;t exist.</h1>
        <p className="text-lg text-muted">The link may be old, or the address may have a typo.</p>
        <div className="flex flex-wrap gap-3">
          <Button asChild><Link href="/">Go to the homepage</Link></Button>
          <Button asChild variant="secondary"><Link href="/dashboard">Open your dashboard</Link></Button>
        </div>
      </div>
    </main>
  );
}
