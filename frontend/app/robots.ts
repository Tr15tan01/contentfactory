import type { MetadataRoute } from "next";
import { absoluteUrl } from "@/lib/site";

// App and auth screens are private; only the marketing site is indexed.
const PRIVATE = ["/api/", "/dashboard", "/content", "/calendar", "/media", "/agent", "/insights", "/intelligence",
  "/settings", "/onboarding", "/admin", "/workspace", "/login", "/register", "/verify-email", "/forgot-password", "/reset-password"];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: PRIVATE }],
    sitemap: absoluteUrl("/sitemap.xml"),
  };
}
