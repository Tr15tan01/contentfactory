# Architecture

## Request flow

```
Browser ──► Next.js (:3000) ──/api/v1/*──► FastAPI (:8000) ──► PostgreSQL + pgvector
              │  proxy.ts (route gating)          │
              │  static marketing pages           ├──► Redis (rate limits, job queue)
              └─ client app (TanStack Query)      └──► arq worker (email, maintenance, later: AI, publishing)
```

- The browser only ever talks to the Next.js origin. `next.config.ts` rewrites `/api/v1/*` to `BACKEND_URL`, so auth cookies are first-party and `SameSite` protections work.
- Marketing pages are statically prerendered. App pages are client-rendered against the API, because the refresh cookie is scoped to `/api/v1/auth` and never reaches the Next.js server.
- `proxy.ts` is routing only, not a security boundary: it redirects visitors without the `cf_signed_in` hint cookie away from app routes, and serves signed-in users the workspace analytics page at `/analytics` (visitors see the marketing page there). Every API call is authorised by FastAPI.

## Backend layout (`backend/app`)

| Package | Responsibility |
| --- | --- |
| `core/` | Settings, database and Redis clients, error envelope, security primitives (Argon2id, JWT, HMAC token hashing, signing), Fernet encryption, CSRF middleware, rate limiting, cookies |
| `models/` | 34 SQLAlchemy models (see [database.md](database.md)) |
| `schemas/` | Pydantic request and response models |
| `auth/` | Auth service, dependencies (`CurrentUser`, `WorkspaceContext`), Google OAuth, router |
| `repositories/` | Query helpers for users and workspaces |
| `services/` | Business logic: dashboard, media library, business profile, audit logging |
| `billing/` | Plan catalogue (single source of truth), entitlements and allowance periods, Paddle client and signature verification, billing service and webhook processing |
| `ai/` | Text and image provider protocols and adapters, offline development providers, embeddings, allowance reservations and response cache |
| `content/` | Platform rules and warnings, prompt builder, content service (generation job, workflow, schedules, versions) |
| `analytics/` | Metrics collector, analytics overview, insights engine |
| `intelligence/` | Marketing memory (embeddings, retrieval) and A/B experiments |
| `agents/` | Agent activity recorder (runs and steps) |
| `notifications/` | Email providers and templates, in-app notifications, approval reminders |
| `social/` | Provider protocol, Meta / TikTok / YouTube adapters, connection service (OAuth, encrypted tokens, refresh), publishing engine |
| `storage/` | Object storage protocol with `local` and `s3` implementations |
| `media/` | Upload policy (types, limits, magic-byte sniffing), post-upload processing, image generation and video assembly |
| `notifications/email/` | Provider protocol, console and Resend providers, templates |
| `workers/` | `JobQueue` protocol, arq settings, job functions |
| `api/v1/` | Health, workspaces, business, media, content, billing, social, intelligence, activity (notifications, agent runs), admin, local storage, public (contact form) routers |

Design rules:

- **Provider abstractions everywhere external.** Email, the job queue, and later AI, storage, social and billing sit behind protocols with a mock or console implementation, so the product runs locally without third-party accounts and tests don't need network access.
- **Services own transactions.** Routers validate and delegate; services stage changes (including audit rows) and commit once.
- **Workspace isolation in one place.** `get_workspace_context` resolves membership for every `/workspaces/{id}/…` route and returns 404 for non-members, so IDs can't be probed.
- **Errors are data.** Every error is `{"error": {"code", "message", "details"}}`; stack traces never leave the server. The frontend maps `code` to specific messages.

## Frontend layout (`frontend/`)

| Path | Contents |
| --- | --- |
| `app/(marketing)/` | Landing page, features, six product pages, pricing, about, FAQ, contact, blog, legal |
| `app/(auth)/` | Login, register, verify email, forgot and reset password (not indexed) |
| `app/(app)/` | Workspace app: dashboard, content list, post editor, create post, calendar, media library, settings (profile, business, security), later-phase routes |
| `app/(focus)/` | Signed-in pages without the sidebar: guided onboarding |
| `components/ui/` | Primitives (button, inputs, field, alert, dialog, dropdown, meter) |
| `components/marketing/`, `components/app/`, `components/auth/` | Feature components |
| `content/` | Copy for feature pages, FAQ and blog posts (typed data, no CMS yet) |
| `lib/api/` | Fetch client (CSRF header, single-flight refresh, error mapping) and typed endpoints |
| `lib/plans.ts` | Mirror of the backend plan catalogue |
| `proxy.ts` | Route gating and the `/analytics` split |
| `lib/uploads.ts` | Direct-to-storage uploads with progress |
| `lib/paddle.ts` | Loads Paddle.js on demand and opens the overlay checkout |
| `lib/zoned.ts` | Workspace time-zone conversions (DST-safe, no date library) |
| `e2e/smoke.py`, `e2e/phase2.py`, `e2e/phase3.py` | Playwright checks for the running stack |

## Design system

Tokens are CSS variables in `app/globals.css`, exposed to Tailwind through `@theme`:

- **Colour:** cool paper background, deep teal ink, brand teal for actions, and a highlighter yellow reserved for one meaning: facts the agent learned from real data. Signal red for failures only.
- **Type:** Instrument Sans, self-hosted from `@fontsource-variable` (no runtime Google request), using its width axis: condensed (75–78%) for headlines, normal width for reading. Numbers use tabular figures.
- **Radius hierarchy:** frames 18px, cards 12px, controls 9px, status chips fully rounded.
- **Motion:** one CSS-driven sequence in the landing hero, a scroll reveal on the calendar that never hides server-rendered content, and a short fade on the dashboard. `prefers-reduced-motion` disables all of it.
- **Themes:** light and dark via `next-themes` (class strategy), defaulting to the system setting.
