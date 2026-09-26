import type { NextConfig } from "next";

// The browser only ever talks to the Next.js origin. /api/v1/* is proxied to FastAPI so that
// auth cookies are first-party, SameSite works, and the backend URL is never exposed.
// BACKEND_URL may be a full URL or a bare "host:port" (e.g. Render's private-network hostport).
// On Render a missing BACKEND_URL would silently bake in localhost, so fail the build instead.
if (process.env.RENDER && !process.env.BACKEND_URL) {
  throw new Error("BACKEND_URL is not set: redeploy once contentfactory-api is live.");
}
const rawBackend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const backend = (/^https?:\/\//.test(rawBackend) ? rawBackend : `http://${rawBackend}`).replace(
  /\/$/,
  "",
);
const isProd = process.env.NODE_ENV === "production";

// Scripts: our own plus Paddle.js (checkout). 'unsafe-inline' is needed for Next.js's inline
// bootstrap without per-request nonces; 'unsafe-eval' only in development (React refresh).
// connect-src allows https: because uploads go straight to the S3-compatible bucket, whose
// host differs per deployment; img-src already allows https: for signed media URLs.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' ${isProd ? "" : "'unsafe-eval' "}https://cdn.paddle.com`,
  "style-src 'self' 'unsafe-inline' https://cdn.paddle.com",
  "img-src 'self' data: blob: https:",
  "media-src 'self' blob: https:",
  "font-src 'self' data:",
  "connect-src 'self' https:",
  "frame-src https://*.paddle.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
  ...((process.env.NEXT_PUBLIC_APP_URL ?? "").startsWith("https://") ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  ...(isProd
    ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" }]
    : []),
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  typedRoutes: false,
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
