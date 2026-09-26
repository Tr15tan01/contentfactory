# ContentFactory

An AI marketing agent for small businesses: it plans, creates, schedules, publishes and improves social content, and learns what works for each business through a persistent Marketing Intelligence memory (no model retraining).

This repository was built in the eight phases of the product spec, and **all eight are complete**: foundation, onboarding and media library, AI drafting with approvals and the calendar, Paddle billing, social accounts with automatic publishing, analytics with insights, memory and experiments, AI images with a video builder, and notifications, agent activity, admin and hardening. See **What isn't built** below for the parts of the spec that are not.

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn-style components on Radix, Lucide, Motion (Framer Motion), TanStack Query |
| Backend | Python 3.13 target (runs on 3.12+), FastAPI, Pydantic 2, SQLAlchemy 2 (async), Alembic, asyncpg |
| Data | PostgreSQL 16 with pgvector, Redis 7 |
| Jobs | arq (Redis-backed async worker) |
| Auth | Custom: Argon2id passwords, rotating refresh sessions, httpOnly cookies, CSRF double-submit, optional Google OAuth |

## Repository layout

```
backend/     FastAPI app, models, migrations, services, worker jobs, tests, demo seed
frontend/    Next.js app: marketing site, auth pages, workspace app, e2e smoke test
workers/     How to run the background worker (code lives in backend/app/workers)
docs/        Architecture, database, auth, billing, integrations, agents, deployment, env
```

## Quick start (local development)

Prerequisites: Python 3.12+ (tested on 3.13), Node 22+, a PostgreSQL 16+ database with the `pgvector` extension, and Redis 7 (or a Redis-compatible server). Optional: `ffmpeg` for video thumbnails, durations and video building.

### 1. Database and Redis

**Windows.** pgvector has no ready-made Windows build, so use a hosted database:

- **PostgreSQL: [Neon](https://neon.tech)** (free tier, pgvector included). In your project click **Connect**, turn **off** "Connection pooling" (the host must not contain `-pooler`), click **Show password** and copy the string. Paste it into `DATABASE_URL` in `backend/.env` exactly as shown; the backend converts `postgresql://…?sslmode=require&channel_binding=require` for asyncpg.
- **Redis: [Memurai Developer](https://www.memurai.com/get-memurai)** (free, Redis-compatible). It installs as a Windows service on port 6379, which matches the default `REDIS_URL`. It stops after 10 days of uptime; restart the Memurai service (or reboot) when that happens. A hosted Redis also works: put its `redis://` or `rediss://` address in `REDIS_URL`.

**Linux / macOS.** Install PostgreSQL 16 with pgvector (`apt install postgresql-16 postgresql-16-pgvector`, or `brew install postgresql@16 pgvector`) and Redis 7, then:

```bash
createuser -s cf && psql -c "ALTER USER cf PASSWORD 'cf'"
createdb -O cf contentfactory && createdb -O cf contentfactory_test
redis-server --daemonize yes
```

The default `DATABASE_URL` in `.env.example` points at this local database.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows Git Bash: source .venv/Scripts/activate
cp .env.example .env                 # set JWT_SECRET and SESSION_SECRET (32+ chars); DATABASE_URL
pip install -e ".[dev]"
alembic upgrade head                 # creates the tables and enables pgvector
python -m scripts.seed_demo          # optional: "Tbilisi Coffee Lab" demo workspace with photos
uvicorn app.main:app --reload --port 8000
```

Check http://localhost:8000/api/v1/health: it should report `"database": "ok"` and `"redis": "ok"`.
Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

### 3. Worker (second terminal)

Runs AI generation, media processing, publishing, email and maintenance. Start it from `backend/` so it shares `var/storage` with the API.

```bash
cd backend
source .venv/bin/activate            # Windows Git Bash: source .venv/Scripts/activate
arq app.workers.settings.WorkerSettings
```

### 4. Frontend (third terminal)

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev                          # http://localhost:3000
```

### Troubleshooting

| Error | Cause and fix |
| --- | --- |
| `ConnectionRefusedError` on `alembic upgrade head` | Nothing is listening at the `DATABASE_URL` host. Start PostgreSQL, or point `DATABASE_URL` at your Neon database. |
| `unexpected keyword argument 'sslmode'` | An old copy of `app/core/config.py`; update it, or write the URL as `postgresql+asyncpg://…?ssl=require` without `channel_binding`. |
| `password authentication failed` | The password was cut off when copying; copy the string again after **Show password**. |
| `prepared statement … does not exist` | You used Neon's pooled (`-pooler`) string; turn pooling off and copy again. |
| `extension "vector" is not available` | Your PostgreSQL doesn't have pgvector; use Neon or install the extension. |
| Health shows `"redis": "error"` | Redis/Memurai isn't running, or `REDIS_URL` is wrong. |

The browser only talks to `http://localhost:3000`; Next.js proxies `/api/v1/*` to FastAPI so auth cookies are first-party.

**Demo login:** `demo@contentfactory.dev` / `demo-coffee-2026` (only after running the seed). Remove it with `python -m scripts.seed_demo --remove`. The seed refuses to run when `ENVIRONMENT=production`.

**Email in development:** `EMAIL_PROVIDER=console` prints each email, including verification and reset links, to the worker log.

**AI in development:** `AI_PROVIDER=mock` uses an offline template writer so the whole product works without an API key. Drafts it writes are labelled in the UI, and the API refuses to start with it in production. Set `AI_PROVIDER=anthropic` or `AI_PROVIDER=gemini` plus a key and model names to use a real model ([docs/environment.md](docs/environment.md#using-gemini), [docs/content-workflow.md](docs/content-workflow.md)).

**Billing in development:** without `PADDLE_*` settings the Billing page says paid plans aren't available and everything else works on Free. Give an account a plan with `python -m scripts.set_plan email business --by you`, or run the full Paddle loop locally as described in [docs/billing.md](docs/billing.md).

**Social accounts in development:** providers without app credentials show as unavailable; nothing is faked. The full connect-and-publish loop can be run locally against a Meta stand-in ([docs/social-integrations.md](docs/social-integrations.md)).

**Images in development:** `AI_IMAGE_PROVIDER=mock` draws labelled placeholders (badged "Placeholder", refused in production). Video building needs `ffmpeg`.

**Files in development:** `STORAGE_PROVIDER=local` stores uploads under `backend/var/storage` and serves them through signed API URLs. Run the API and worker from `backend/` so they share that folder. Production uses S3-compatible storage ([docs/media-storage.md](docs/media-storage.md)).

## Tests

```bash
cd backend && python -m pytest -q          # 99 tests; uses the contentfactory_test database (or TEST_DATABASE_URL); never reads .env
cd backend && ruff check . && ruff format --check . && alembic check
cd frontend && npm run lint && npm run build  # ESLint (Next config), type-check, prerender 43 pages
cd frontend && python3 e2e/smoke.py         # 16 browser checks: auth, dashboard, routing (Playwright)
cd frontend && python3 e2e/phase2.py        # 15 browser checks: onboarding, uploads, media library
cd frontend && python3 e2e/phase3.py        # 13 browser checks: AI drafts, approval, scheduling, calendar
cd frontend && python3 e2e/phase4.py        # 13 browser checks: billing via signed Paddle webhooks (see docs/billing.md)
cd frontend && python3 e2e/phase5.py        # 10 browser checks: Meta OAuth connect and scheduled publishing (see docs/social-integrations.md)
cd frontend && python3 e2e/phase6.py        # 9 browser checks: analytics, insights, memory, experiments (demo business)
cd frontend && python3 e2e/phase7.py        # 9 browser checks: image generation and reuse, video builder, generate into a post
cd frontend && python3 e2e/phase8.py        # 10 browser checks: reminders and the bell, settings, agent activity, admin, CSP
```

The backend tests wipe and rebuild their database on every run, so never point them at your main database. With Neon, create a second database (for example `contentfactory_test`) and export its connection string before running them: `export TEST_DATABASE_URL='postgresql://…'`. Tests use an in-memory Redis, so they don't need Redis running.

Running the browser suites many times in an hour trips the sign-up rate limit (10 per IP per hour) by design; in development clear it with `redis-cli --scan --pattern 'rl:*' | xargs -r redis-cli del`.

Backend tests cover notifications (reminders at chosen offsets, no duplicates, overdue notices, preferences, email delivery), agent activity records, the admin area (access, suspension ending sessions, audit), structural guards that every write endpoint checks roles, image generation (brand prompts, reuse without charge, refunds, allowance limits, the OpenAI-compatible adapter) and video assembly (a real ffmpeg render, credit cost by length, reuse, limits), metrics collection (unreported metrics stay null), analytics totals, insight evidence thresholds, save-to-memory, memory search and its use in AI drafts, experiments and plan limits, social accounts and publishing (OAuth state, plan account limits, encrypted tokens, idempotent scheduling, retries that reuse the same upload, expired access, unknown outcomes, overdue approvals, retry on the original account, TikTok and YouTube adapters, token refresh), billing (webhook signatures and replay window, idempotent delivery, out-of-order events, unknown prices, forged checkout data, past-due and cancellation rules, downgrade constraints, Paddle API calls, support overrides), AI drafting (quota reservation, cache reuse at no charge, refunds on failure, one repair retry, media the model wasn't offered is ignored, prompt data containment, the Anthropic adapter over HTTP), the approval and scheduling workflow, versions, calendar queries, scheduled-post quotas, media uploads (type and size limits, disguised files, upload-link tampering, duplicates, search, folders, video processing with ffmpeg, S3 via moto), the business profile (validation, plan-gated approval settings, products with media, onboarding), registration and verification, login lockout, refresh-token rotation and reuse detection, password reset, session revocation, account deletion, CSRF, cross-workspace isolation (404, not 403), role checks, dashboard empty states, insight sample-size gating, time-zone validation, crypto, and a check that the frontend plan catalogue matches the backend.

The e2e smoke test registers a user through the UI, confirms the email using the link the worker actually sent, changes the password, signs out and in, verifies redirects and the demo dashboard.

## Product rules the code enforces

- Never fake social APIs, analytics or published state. Missing platform metrics are `NULL` and shown as "Not available from this platform".
- Never promise unlimited AI. Every plan has monthly quotas (`backend/app/billing/plans.py` is the source of truth; `frontend/lib/plans.ts` mirrors it and a test fails on drift).
- Insights are hidden until they have a minimum sample (`MIN_INSIGHT_SAMPLE = 8`) and always show sample size and period.
- Nothing publishes without approval unless the user turns on autopilot (Business and Agency).

## Build phases

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Structure, schema (34 tables), design system, auth, marketing site, dashboard foundation | **Done** |
| 2 | Onboarding, business profile, media library, S3 storage | **Done** |
| 3 | AI provider abstraction, content generation, calendar, approvals | **Done** |
| 4 | Paddle billing, entitlements, quota enforcement, AI credits | **Done** |
| 5 | Social OAuth adapters, publishing engine | **Done** (not yet run against the real platform APIs) |
| 6 | Analytics collection, Marketing Intelligence, memory retrieval, experiments | **Done** (metrics collection not yet run against the real platform APIs) |
| 7 | AI images and video | **Done**: images via an OpenAI-compatible API (not yet run against a real one); videos assembled from own media. Text-to-video not included. |
| 8 | Notifications, agent activity page, admin area, hardening | **Done** |

App screens for later phases exist as routes that describe what they will do and never show placeholder data.

## What isn't built

Everything below was in the product spec and is **not** in this codebase:

- **Autopilot as an agent that plans and schedules on its own.** Business and Agency can publish without approval, and every draft is agent-written on request, but no scheduled job plans a week of content by itself. The Strategy and Research agents from the spec don't exist yet.
- **Text-to-video, AI-generated video scenes and voiceovers.** Videos are assembled from the business's own media.
- **LinkedIn, Pinterest and X** publishing (shown as planned), and **choosing between several accounts** on one platform (the first connected is used).
- **Push notifications** (in-app and email only), and multi-business management UI for the Agency plan (the data model supports several workspaces; creating more from the UI isn't there).

And these are built but **not yet verified against the real services**: Anthropic text generation, the OpenAI-compatible image API, Paddle, Meta, TikTok, YouTube, and metrics collection. Every check used faithful stand-ins; each needs one real run in the provider's test mode before launch (see each doc's "Before launch").

## Documentation

- **[Deploying on Render](docs/deploy-render.md)**: one web service (free plan works, `render-build.sh` / `render-start.sh`) or the `render.yaml` Blueprint
- [Architecture](docs/architecture.md)
- [Database](docs/database.md)
- [Authentication](docs/auth.md)
- [Media library and storage](docs/media-storage.md)
- [Content, AI drafting and approvals](docs/content-workflow.md)
- [Billing and quotas](docs/billing.md)
- [Social accounts and publishing](docs/social-integrations.md)
- [Analytics, insights, memory and experiments](docs/analytics-intelligence.md)
- [AI images and video](docs/ai-media.md)
- [Notifications, agent activity, admin and security](docs/operations.md)
- [Social integrations](docs/social-integrations.md)
- [AI agents](docs/ai-agents.md)
- [Deployment](docs/deployment.md)
- [Environment variables](docs/environment.md)
