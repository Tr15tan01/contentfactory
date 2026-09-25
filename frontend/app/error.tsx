"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return (
    <main id="main" className="grid min-h-[60dvh] place-items-center px-6 py-16">
      <div className="grid max-w-md gap-5">
        <h1 className="display text-4xl">This page didn&apos;t load.</h1>
        <p className="text-muted">
          Something failed on our side. Your work is saved. Try again, and if it keeps happening, contact support
          {error.digest ? <> with reference <code className="rounded bg-sunk px-1.5 py-0.5 text-sm">{error.digest}</code></> : null}.
        </p>
        <div>
          <Button onClick={reset}>Try again</Button>
        </div>
      </div>
    </main>
  );
}
