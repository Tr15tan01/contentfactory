"use client";

import { useEffect, useState } from "react";
import { authApi } from "@/lib/api/endpoints";
import type { AuthConfig } from "@/types/api";

const DEFAULTS: AuthConfig = { google_enabled: false, email_verification_required: true, password_min_length: 10 };
let cached: AuthConfig | null = null;

/** Server-driven auth switches (AUTH_GOOGLE_ENABLED, AUTH_REQUIRE_EMAIL_VERIFICATION). */
export function useAuthConfig(): AuthConfig {
  const [config, setConfig] = useState<AuthConfig>(cached ?? DEFAULTS);
  useEffect(() => {
    if (cached) return;
    authApi
      .config()
      .then((c) => {
        cached = c;
        setConfig(c);
      })
      .catch(() => undefined);
  }, []);
  return config;
}
