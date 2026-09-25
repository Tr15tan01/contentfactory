"use client";

import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/api/endpoints";

export function GoogleButton({ next, label = "Continue with Google" }: { next?: string; label?: string }) {
  return (
    <>
      <Button asChild variant="secondary" size="lg" className="w-full">
        {/* Full navigation: the OAuth flow is server-side with PKCE and a signed state cookie. */}
        <a href={authApi.googleStartUrl(next)}>
          {label}
        </a>
      </Button>
      <div className="flex items-center gap-3 text-sm text-faint">
        <span className="h-px flex-1 bg-line" /> or with email <span className="h-px flex-1 bg-line" />
      </div>
    </>
  );
}
