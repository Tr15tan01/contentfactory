# Environment variables

Backend settings are read by `backend/app/core/config.py` (pydantic-settings) from the environment or `backend/.env`. Start from `backend/.env.example`. Booleans accept `1/0`, `true/false`.

## Core

| Variable | Default | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `development`, `test`, `staging`, `production`. Production enables strict validation and disables API docs. |
| `APP_URL` | `http://localhost:3000` | Public origin of the Next.js app. Used in emails, OAuth redirects and CSRF origin checks. |
| `API_PREFIX` | `/api/v1` | |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins (`APP_URL` is always allowed for CSRF origin checks). |
| `RUN_WORKER_IN_API` | `0` | `1` runs the background worker (jobs and schedules) inside the API process, so a small deployment needs one backend service. Leave `0` when a separate `arq` worker runs. |
| `WORKER_MAX_JOBS` | `20` | Jobs a worker runs at once. Use `2` on 512 MB instances. |
| `TRUSTED_PROXY_COUNT` | `1` | `X-Forwarded-For` hops to trust, counted from the right. Next.js passes the header through unchanged, so count the proxies in front of Next.js. Render: `3` (client, Cloudflare, Render proxy). |
| `LOG_LEVEL` | `INFO` | |
| `DATABASE_URL` | local | Must use the `postgresql+asyncpg://` driver. |
| `DATABASE_POOL_SIZE` | `10` | Per process. |
| `REDIS_URL` | `redis://localhost:6379/0` | Rate limits and the job queue. |

## Security and auth

| Variable | Default | Notes |
| --- | --- | --- |
| `JWT_SECRET` | required | 32+ characters. Signs access tokens. |
| `SESSION_SECRET` | required | 32+ characters. Keys token hashes and signed cookies. Rotating it signs everyone out. |
| `ENCRYPTION_KEYS` | empty | Comma-separated Fernet keys; first encrypts. **Required in production.** |
| `AUTH_REQUIRE_EMAIL_VERIFICATION` | `1` | |
| `AUTH_GOOGLE_ENABLED` | `0` | Requires `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. |
| `ACCESS_TOKEN_TTL_MINUTES` | `15` | |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | |
| `REFRESH_REUSE_GRACE_SECONDS` | `15` | Concurrent-refresh window. |
| `EMAIL_VERIFICATION_TTL_HOURS` | `48` | |
| `PASSWORD_RESET_TTL_MINUTES` | `30` | |
| `PASSWORD_MIN_LENGTH` | `10` | Also sent to the frontend via `/auth/config`. |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCKOUT_MINUTES` | `5` / `15` | |
| `COOKIE_SECURE` | `1` | Must be `1` in production. Set `0` only for plain-HTTP local development. |
| `COOKIE_DOMAIN` | unset | Host-only cookies by default. |

## Email

| Variable | Default | Notes |
| --- | --- | --- |
| `EMAIL_PROVIDER` | `console` | `console` (dev, prints to worker log; rejected in production) or `resend`. |
| `EMAIL_PROVIDER_API_KEY` | | |
| `EMAIL_FROM` | `ContentFactory <hello@contentfactory.app>` | Must be a verified sender domain. |
| `SUPPORT_EMAIL` | `support@contentfactory.app` | Receives contact-form messages. |

## Storage and media (Phase 2)

| Variable | Default | Notes |
| --- | --- | --- |
| `STORAGE_PROVIDER` | `local` | `local` (files on disk, signed API URLs; refused in production) or `s3`. |
| `STORAGE_LOCAL_DIR` | `var/storage` | Relative to the working directory of the API **and** worker, which must share it. |
| `STORAGE_URL_TTL_SECONDS` | `3600` | Lifetime of signed download URLs (bucketed so browsers can cache). |
| `MEDIA_MAX_IMAGE_MB` / `MEDIA_MAX_VIDEO_MB` | `25` / `500` | Upload limits, enforced by storage (S3 policy) and the API. Keep `frontend/lib/uploads.ts` in step for instant client-side messages. |
| `STORAGE_ENDPOINT` | empty | S3-compatible endpoint; empty for AWS. |
| `STORAGE_REGION` | `auto` | |
| `STORAGE_BUCKET` | `contentfactory` | |
| `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` | empty | Credentials limited to the bucket. |
| `STORAGE_UPLOAD_METHOD` | `post` | `post` (presigned POST: AWS S3, MinIO) or `put` (presigned PUT: required for Cloudflare R2). |

Bucket setup and CORS: [media-storage.md](media-storage.md).

## AI text (Phase 3)

| Variable | Default | Notes |
| --- | --- | --- |
| `AI_PROVIDER` | `mock` | `mock` (offline template writer, labelled in the UI, **refused in production**), `anthropic` or `gemini`. |
| `AI_PROVIDER_API_KEY` | empty | Required for a real provider. |
| `AI_FAST_MODEL` / `AI_REASONING_MODEL` | empty | Model names for each role. Required for a real provider. |
| `AI_API_BASE_URL` | `https://api.anthropic.com` | Anthropic only. Override for a proxy or gateway. |
| `GEMINI_API_BASE_URL` | `https://generativelanguage.googleapis.com` | Gemini text, images and embeddings. |
| `AI_FAST_THINKING_LEVEL` / `AI_REASONING_THINKING_LEVEL` | `low` / `medium` | Gemini only: `minimal`, `low`, `medium`, `high`, or empty for the model default. Thinking tokens are billed as output. |
| `AI_TIMEOUT_SECONDS` | `90` | Per provider call. |
| `AI_CACHE_TTL_HOURS` | `336` | How long identical requests reuse a stored result (free). |
| `AI_{FAST,REASONING}_{INPUT,OUTPUT}_USD_PER_MTOK` | `0` | Optional prices for cost tracking in `ai_usage`. |

Details: [content-workflow.md](content-workflow.md).

## Billing (Phase 4)

| Variable | Default | Notes |
| --- | --- | --- |
| `BILLING_ENABLED` | `1` | `0` launches without paid plans: Paddle isn't required in production and everyone is on Free (plans granted with `scripts.set_plan` still apply). |
| `PADDLE_ENVIRONMENT` | `sandbox` | `sandbox` or `production`; selects the API host and Paddle.js environment. |
| `PADDLE_API_KEY` | empty | Server-side API key. |
| `PADDLE_CLIENT_TOKEN` | empty | Public token for Paddle.js checkout. |
| `PADDLE_WEBHOOK_SECRET` | empty | Endpoint secret for signature verification. |
| `PADDLE_STARTER_PRICE_ID` / `PADDLE_BUSINESS_PRICE_ID` / `PADDLE_AGENCY_PRICE_ID` | empty | Monthly price ids. |
| `PADDLE_API_BASE_URL` | empty | Override the API host (proxy or local test stand-in). |

All `PADDLE_*` values except the base URL are **required in production**. Without them in development, paid plans are shown as unavailable.

## Social accounts (Phase 5)

| Variable | Default | Notes |
| --- | --- | --- |
| `META_CLIENT_ID` / `META_CLIENT_SECRET` | empty | Meta app for Instagram and Facebook Pages. Empty = provider unavailable. |
| `META_GRAPH_VERSION` | `v21.0` | Graph API version. |
| `META_GRAPH_BASE_URL` / `META_DIALOG_BASE_URL` | empty | Host overrides for proxies or local test stand-ins. |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | empty | TikTok app. Empty = provider unavailable. |
| `YOUTUBE_ENABLED` | `1` | YouTube uses `GOOGLE_CLIENT_ID/SECRET` (with the `youtube.upload` scope); set `0` to hide it. |

The **worker** needs the same values as the API: it publishes and refreshes tokens. Without `ENCRYPTION_KEYS` in development, the token key is derived from `SESSION_SECRET` so API and worker agree; production requires `ENCRYPTION_KEYS`.

## Memory embeddings (Phase 6)

| Variable | Default | Notes |
| --- | --- | --- |
| `AI_EMBEDDING_PROVIDER` | `local` | `local` (in-process lexical hashing, no API), `voyage` or `gemini`. After switching, run `python -m scripts.reembed_memory`. |
| `AI_EMBEDDING_MODEL` / `AI_EMBEDDING_API_KEY` | empty | Model name and key. For `gemini` the key falls back to `AI_PROVIDER_API_KEY`. |
| `AI_EMBEDDING_DIMENSIONS` | `1536` | Must match the vector column. Changing provider or dimensions means re-embedding existing memories. |

## AI images and video (Phase 7)

| Variable | Default | Notes |
| --- | --- | --- |
| `AI_IMAGE_PROVIDER` | `mock` | `mock` (labelled development placeholder, **refused in production**), `openai` (any OpenAI-compatible images API) or `gemini` (native Gemini image models). |
| `AI_IMAGE_MODEL` / `AI_IMAGE_API_KEY` | empty | Required for a real provider. For `gemini` the key falls back to `AI_PROVIDER_API_KEY`. |
| `AI_IMAGE_API_BASE_URL` | `https://api.openai.com/v1` | Point at any compatible provider or gateway. |
| `VIDEO_FONT_PATH` | empty (auto) | Font for on-screen text in built videos. Empty or missing = first found of DejaVu Sans Bold (Linux), Arial Bold (Windows, macOS). With no font, videos are built without text. |

The video builder needs `ffmpeg` on the worker.

## Integrations (used from later phases)

| Group | Variables |
| --- | --- |
| Not yet used | `AI_VIDEO_MODEL`, `AI_VOICE_MODEL` (text-to-video and voiceover aren't implemented) |
| Web push (Phase 8) | `PUSH_PUBLIC_KEY`, `PUSH_PRIVATE_KEY` |

`AI_EMBEDDING_DIMENSIONS` must match the vector column; changing it after the first migration requires a migration and re-embedding.

## Frontend (`frontend/.env.local`)

| Variable | Default | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_APP_URL` | `http://localhost:3000` | Canonical URLs, sitemap, Open Graph. Set at build time. |
| `BACKEND_URL` | `http://127.0.0.1:8000` | Where Next.js proxies `/api/v1/*`. Server-side only. |

## Using Gemini

One key from [Google AI Studio](https://aistudio.google.com/apikey) covers text, images and embeddings:

```dotenv
AI_PROVIDER=gemini
AI_PROVIDER_API_KEY=your-gemini-key
AI_FAST_MODEL=gemini-3.5-flash-lite
AI_REASONING_MODEL=gemini-3.8-flash
AI_IMAGE_PROVIDER=gemini
AI_IMAGE_MODEL=gemini-3.1-flash-image
AI_EMBEDDING_PROVIDER=gemini
AI_EMBEDDING_MODEL=gemini-embedding-001
AI_EMBEDDING_DIMENSIONS=1536
```

Model names change; check Google's model list before deploying. Image generation has no free tier. After switching embeddings, run `python -m scripts.reembed_memory`.
