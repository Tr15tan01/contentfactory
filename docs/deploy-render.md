# Deploying on Render

Two ways to deploy, both redeploying automatically on every push to `main`:

| | A. One web service (free plan works) | B. Blueprint (`render.yaml`, paid) |
| --- | --- | --- |
| Services | 1 web service running the website, API and background worker together, plus a Key Value (Redis) | Separate API, worker and website services, plus Key Value |
| Cost | Free instance + free Key Value | 3 paid instances + paid Key Value |
| Good for | Trying it out, first customers | Growing traffic, reliable schedules, video |

Both use Neon for PostgreSQL, Cloudflare R2 (or S3) for files, Resend for email and Gemini for AI. Section 1 lists what to prepare; it applies to both.

## 1. Before you start

Have these ready before creating anything on Render.

1. **Production database.** Use a separate Neon database or branch for production, not the one you developed against: that one contains the demo account, whose password is public in this README. In Neon, create a branch or database, click **Connect**, turn off **Connection pooling**, and copy the string.
2. **Gemini API key** from [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
3. **Email (Resend).** Sign-up requires email verification in production. Create a [Resend](https://resend.com) account, verify your sending domain, and create an API key. `EMAIL_FROM` must use that domain.
4. **Storage (Cloudflare R2).** Create a bucket, then an R2 API token with *Object Read & Write* on it. Note the account ID, access key and secret. Add this CORS policy to the bucket (use your real frontend URL):
   ```json
   [{"AllowedOrigins": ["https://contentfactory-web.onrender.com"],
     "AllowedMethods": ["PUT", "GET", "HEAD"],
     "AllowedHeaders": ["*"], "ExposeHeaders": ["ETag"], "MaxAgeSeconds": 3600}]
   ```
   Using AWS S3 instead: set `STORAGE_UPLOAD_METHOD=post`, `STORAGE_REGION` to the bucket's region, leave `STORAGE_ENDPOINT` empty, and allow `POST` in CORS.
5. **Encryption key** for social-account tokens:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Keep a copy somewhere safe: losing it means everyone has to reconnect their social accounts.

## A. One web service (the usual "New Web Service" way)

`render-build.sh` and `render-start.sh` in the repo root make the whole app run as one service: the website on Render's public port, the API (with the background worker inside it, `RUN_WORKER_IN_API=1`) on a private port behind it, and database migrations on every start.

1. **Redis.** New → **Key Value**: name `contentfactory-redis`, region **Frankfurt** (next to Neon's `eu-central-1`), plan **Free**, maxmemory policy **noeviction**. Copy its **Internal Key Value URL**.
2. **Web service.** New → **Web Service** → your repo, then:

| Field | Value |
| --- | --- |
| Language | Python 3 |
| Branch | `main` |
| Region | Frankfurt (same as the Key Value) |
| Root Directory | *(leave empty)* |
| Build Command | `bash render-build.sh` |
| Start Command | `bash render-start.sh` |
| Instance Type | Free (or any paid size) |

3. **Environment.** Under **Environment Variables** click **Add from .env**, paste this and fill in the blanks (section 1 says where each value comes from):

```dotenv
PYTHON_VERSION=3.13.13
ENVIRONMENT=production
RUN_WORKER_IN_API=1
WORKER_MAX_JOBS=2
COOKIE_SECURE=1
TRUSTED_PROXY_COUNT=3
AUTH_REQUIRE_EMAIL_VERIFICATION=1
BILLING_ENABLED=0
REDIS_URL=
DATABASE_URL=
APP_URL=https://<service-name>.onrender.com
CORS_ORIGINS=https://<service-name>.onrender.com
NEXT_PUBLIC_APP_URL=https://<service-name>.onrender.com
JWT_SECRET=
SESSION_SECRET=
ENCRYPTION_KEYS=
EMAIL_PROVIDER=resend
EMAIL_PROVIDER_API_KEY=
EMAIL_FROM=ContentFactory <hello@yourdomain.com>
SUPPORT_EMAIL=
STORAGE_PROVIDER=s3
STORAGE_UPLOAD_METHOD=put
STORAGE_REGION=auto
STORAGE_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
STORAGE_BUCKET=
STORAGE_ACCESS_KEY=
STORAGE_SECRET_KEY=
AI_PROVIDER=gemini
AI_PROVIDER_API_KEY=
AI_FAST_MODEL=gemini-3.5-flash-lite
AI_REASONING_MODEL=gemini-3.8-flash
AI_IMAGE_PROVIDER=gemini
AI_IMAGE_MODEL=gemini-3.1-flash-image
AI_EMBEDDING_PROVIDER=gemini
AI_EMBEDDING_MODEL=gemini-embedding-001
AI_EMBEDDING_DIMENSIONS=1536
```

   `JWT_SECRET` and `SESSION_SECRET`: `python -c "import secrets; print(secrets.token_urlsafe(48))"`, a different value for each. `APP_URL`, `CORS_ORIGINS` and `NEXT_PUBLIC_APP_URL` are the service's own URL, shown at the top of its page once created; if it differs from what you entered, fix all three and redeploy (`NEXT_PUBLIC_APP_URL` is built into the website).

4. **Deploy.** The log should show `Python version 3.13.13`, `pip install ./backend`, `npm ci` and the Next.js build, then at start-up `Running upgrade …` (first deploy only), `Starting worker for … functions` and `Application startup complete`.
5. **Check.** `https://<service-name>.onrender.com/api/v1/health` returns `"database": "ok", "redis": "ok"`. Sign up, verify your email, then see section 3.

### What the free plan means

- **It sleeps.** After 15 minutes without visitors the service stops, and the next visit waits about a minute. While it sleeps nothing runs, so **scheduled posts publish late** (as soon as it wakes). To keep it awake, point a free uptime monitor (UptimeRobot, cron-job.org) at `/api/v1/health` every 10 minutes. One service running all month uses about 744 of the workspace's 750 free hours, so don't run other free services in the same Render workspace; if the hours run out, Render suspends free services until the next month.
- **Free Key Value keeps nothing on disk.** After a Redis restart, queued jobs are gone. The app recovers: scheduled posts are rebuilt from the database every minute, and drafts, images, videos and uploads stuck mid-way are re-queued within about 10–50 minutes (`recover_lost_jobs`). Login rate-limit counters reset.
- **512 MB of memory.** Idle, the website and API use about 230 MB together. `WORKER_MAX_JOBS=2` keeps jobs from piling up; long videos may still fail on the free size.
- **No Shell tab on free.** Run support scripts (`set_admin`, `set_plan`) from your own computer with `DATABASE_URL` in `backend/.env` temporarily pointed at the production database.
- **The disk is wiped** on every deploy, restart or sleep, which is why files go to R2.

Moving to a paid instance later only means changing the instance type; nothing else changes.

## B. Blueprint (separate services, paid)

`render.yaml` in the repo root is a Render Blueprint that creates everything in one go:

| Resource | Type | What it runs |
| --- | --- | --- |
| `contentfactory-api` | Web service (Python) | FastAPI; runs `alembic upgrade head` before each deploy |
| `contentfactory-worker` | Background worker (Python) | arq jobs: AI, media, video (ffmpeg is preinstalled), publishing, email |
| `contentfactory-web` | Web service (Node) | Next.js; proxies `/api/v1/*` to the API over the private network |
| `contentfactory-redis` | Key Value | Job queue, rate limits (persistent, `noeviction`) |

Create it with **New → Blueprint** (a service created with "New Web Service" ignores `render.yaml`). Steps 2–3 below walk through it.

## 2. Create the Blueprint (option B)

1. Push the repo to GitHub (with `render.yaml` at the root).
2. If an earlier manual attempt created a service, delete it (Settings → Delete service).
3. Render dashboard → **New → Blueprint** → choose the repo → **Connect**.
4. Fill in the values it asks for. The API and the worker ask for the same set; enter identical values in both.

| Setting | Value |
| --- | --- |
| `DATABASE_URL` | Neon direct connection string, pasted as-is |
| `APP_URL`, `CORS_ORIGINS`, `NEXT_PUBLIC_APP_URL` | `https://contentfactory-web.onrender.com` (the frontend's URL; see step 3 if Render gives a different one) |
| `ENCRYPTION_KEYS` | the key from step 1.5 |
| `AI_PROVIDER_API_KEY` | Gemini key |
| `EMAIL_PROVIDER_API_KEY` | Resend key |
| `EMAIL_FROM` | `ContentFactory <hello@yourdomain.com>` |
| `SUPPORT_EMAIL` | an address you read |
| `STORAGE_ENDPOINT` | `https://<account-id>.r2.cloudflarestorage.com` |
| `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY` | from R2 |

5. **Apply.** Render creates Redis, builds the API (which migrates the database), the worker and the frontend.

## 3. After the first deploy

- **Frontend URL.** If Render named it something other than `contentfactory-web.onrender.com` (the name was taken), update `APP_URL` and `CORS_ORIGINS` on the API and worker, `NEXT_PUBLIC_APP_URL` on the web service and the R2 CORS rule, then redeploy all three.
- **(Option B) Frontend build failed with "BACKEND_URL is not set".** The frontend was built before the API existed. Once the API shows *Live*, open `contentfactory-web` → **Manual Deploy → Deploy latest commit**.
- **Health.** `/api/v1/health` on the website's URL (option A) or `https://contentfactory-api.onrender.com/api/v1/health` (option B) should return `"database": "ok", "redis": "ok"`.
- **Sign up** on the website, verify your email, then make yourself an admin: from the API's **Shell** tab (paid instances) run `python -m scripts.set_admin you@example.com --by "You"`; on the free plan run the same command on your own computer with `DATABASE_URL` in `backend/.env` pointed at the production database, then point it back.
- **Client IPs.** Open Settings → Security: the current session should show your real public IP. If it shows a `10.x` or Cloudflare address, adjust `TRUSTED_PROXY_COUNT` in the env group (it counts `X-Forwarded-For` entries from the right) and redeploy. Rate limits depend on this being right.

## Settings worth knowing

- **Billing.** `BILLING_ENABLED=0` launches on the Free plan without Paddle. To sell plans, set it to `1` in the env group and add all `PADDLE_*` values to the API and worker ([billing.md](billing.md)). Until then you can grant plans with `python -m scripts.set_plan email business --by you` from the Shell.
- **Social publishing** needs the platform app credentials (`META_*`, `TIKTOK_*`, `GOOGLE_*`) on both the API and the worker ([social-integrations.md](social-integrations.md)). Without them, platforms show as unavailable.
- **Region.** Everything is in Frankfurt to sit next to a Neon database in `eu-central-1`. If your database is elsewhere, change the four `region:` lines in `render.yaml` before creating the Blueprint.
- **Python** is pinned to 3.13 (`PYTHON_VERSION` in the env group); the suite is tested on 3.13.
- **Instance sizes (option B)** default to Render's smallest paid size. The worker may need more memory for video rendering (`plan: 1c-2g`). The API can't use the free plan: free services can't receive private-network traffic or run the pre-deploy migration.
