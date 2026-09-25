# Deployment

## Processes

| Process | Command | Scale |
| --- | --- | --- |
| Web | `cd frontend && npm ci && npm run build && npm start` | Horizontally; stateless |
| API | `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers` (or gunicorn with uvicorn workers) | Horizontally; stateless |
| Worker | `cd backend && arq app.workers.settings.WorkerSettings` | One or more. Runs the scheduled jobs: publishing (every minute), notification emails (every minute), approval reminders (every 15 minutes), token refresh and metrics (hourly), intelligence (nightly). Cron jobs are marked unique, so several workers don't double-run them. Install `ffmpeg` for video thumbnails and durations (optional). |
| Migrations | `cd backend && alembic upgrade head` | Once per release, **before** new API/worker processes start |

Managed services: PostgreSQL 16 with `pgvector` (e.g. Neon, Supabase, RDS, Cloud SQL), Redis 7 with persistence for the queue, and an S3-compatible bucket with the CORS rule in [media-storage.md](media-storage.md).

## Networking

- Serve only the Next.js app publicly over HTTPS. The API can stay private; Next.js reaches it via `BACKEND_URL`.
- If a load balancer sits in front of Next.js, set `TRUSTED_PROXY_COUNT=2` so rate limits and audit logs see the real client IP.
- Health checks: `GET /api/v1/health` returns 200 when database and Redis are reachable and 503 otherwise. Use it for readiness, not liveness, so a database blip doesn't restart every API process.
- `/analytics` is served differently to signed-in users (via `proxy.ts`). If a CDN caches HTML, exclude `/analytics` or vary on the `cf_signed_in` cookie.

## Production checklist

- [ ] `ENVIRONMENT=production` (the API refuses to start with unsafe settings: `COOKIE_SECURE=0`, empty `ENCRYPTION_KEYS`, `EMAIL_PROVIDER=console`)
- [ ] Unique random `JWT_SECRET`, `SESSION_SECRET` (32+ chars) and Fernet `ENCRYPTION_KEYS` from a secret manager
- [ ] `APP_URL` and `NEXT_PUBLIC_APP_URL` set to the real HTTPS origin; `CORS_ORIGINS` limited to it
- [ ] Email provider domain verified (SPF, DKIM, DMARC); `EMAIL_FROM` on that domain
- [ ] Google OAuth redirect URI `{APP_URL}/api/v1/auth/google/callback` registered, if enabled
- [ ] Database backups with point-in-time recovery; Redis persistence enabled
- [ ] `AI_PROVIDER` set to a real provider with `AI_PROVIDER_API_KEY`, `AI_FAST_MODEL` and `AI_REASONING_MODEL` (the API refuses `mock` in production); set the per-token prices if you want cost tracking
- [ ] Paddle: all `PADDLE_*` values set (the API refuses to start without them in production), the three monthly prices created, and a webhook destination `https://<app>/api/v1/billing/webhooks/paddle` subscribed to the `subscription.*` events listed in [billing.md](billing.md)
- [ ] Social apps created (Meta, TikTok, Google) with redirect URIs `{APP_URL}/api/v1/social/callback/{meta,tiktok,youtube}`, credentials given to **both API and worker**, and platform reviews submitted (see [social-integrations.md](social-integrations.md))
- [ ] `AI_IMAGE_PROVIDER=openai` with `AI_IMAGE_MODEL` and `AI_IMAGE_API_KEY` (the API refuses the placeholder generator in production); `ffmpeg` and a font installed on workers for the video builder
- [ ] `STORAGE_PROVIDER=s3` with a private bucket, bucket-scoped credentials and the CORS rule (the API refuses `local` in production)
- [ ] An administrator granted with `python -m scripts.set_admin email --by "Name"`
- [ ] Demo seed **not** run (it refuses in production anyway)
- [ ] **Terms of Service and Privacy Policy reviewed by a lawyer for your jurisdiction.** The pages in `frontend/app/(marketing)/terms` and `privacy` are a plain-language starting point, not legal advice.
- [ ] Sub-processor list (hosting, email, AI providers, storage, Paddle) published and matching the privacy policy
- [ ] Error monitoring and log aggregation (the API logs errors server-side and never returns stack traces)
- [ ] HSTS is sent by Next.js in production; confirm the domain is HTTPS-only before submitting to the preload list

## Release flow

1. Build and test: `pytest`, `npm run build`, then the e2e smoke test against staging.
2. Run `alembic upgrade head` against production. Migrations are written to be backwards-compatible with the previous release (add columns nullable, backfill, then tighten in a later release).
3. Deploy the worker, then the API, then the web app.
4. Watch `/api/v1/health`, error rates and the worker queue length.

## Rotating secrets

- `ENCRYPTION_KEYS`: prepend a new key, deploy, run the re-encryption job, then remove the old key.
- `SESSION_SECRET`: invalidates refresh tokens and verification/reset links, which signs everyone out. Plan it.
- `JWT_SECRET`: invalidates access tokens only; clients refresh transparently.
