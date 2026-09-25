# Content, AI drafting and approvals

**Status:** implemented in Phase 3. Covered by `backend/tests/test_content.py` (11 tests) and the browser test `frontend/e2e/phase3.py`.

## AI provider layer (`backend/app/ai/`)

| Piece | What it does |
| --- | --- |
| `base.py` | `AIProvider` protocol. Callers name a **role** (`fast`, `reasoning`), never a model. `parse_json` tolerates code fences and preamble. |
| `anthropic.py` | Messages API over plain HTTP (testable with `httpx.MockTransport`). 429/5xx/529 are *retryable* errors; other 4xx are not. Optional per-token prices turn usage into cost. |
| `mock.py` | Offline template writer for development and tests. Returns the same JSON shape a real model is asked for. **Refused when `ENVIRONMENT=production`**, and every draft it writes is labelled in the UI. |
| `usage.py` | Monthly allowance accounting (see below) and the response cache. |

Switch providers with `AI_PROVIDER=anthropic`, `AI_PROVIDER_API_KEY`, `AI_FAST_MODEL`, `AI_REASONING_MODEL`; the API refuses to start with a real provider but missing keys or models. Adding another vendor means one class implementing `model_for` and `complete`.

## Allowance, caching, refunds

1. **Reserve** one AI draft before any work, inside a row lock on the workspace, so parallel requests can't both take the last one. Over the limit returns `402 quota_exceeded` with `limit`, `used` and `resets_at`, and the provider is never called.
2. The worker builds the prompt and computes a **fingerprint** (provider, model, system prompt, prompt). An identical request within `AI_CACHE_TTL_HOURS` reuses the stored result and the reservation is committed at **0 credits**.
3. On success the reservation is **committed** with tokens, model and estimated cost.
4. On any failure (provider outage, unusable output after one repair attempt) it is **refunded**, the post is marked `failed` with a message saying the allowance wasn't used, and the user can try again.

Plan allowances come from `app/billing/plans.py` (Free 10, Starter 60, Business 250, Agency 700 per calendar month). Scheduled posts are limited per calendar month the same way (10 / 100 / 500 / 2,000).

## How a draft is written (`backend/app/content/`)

- **Context** comes from the business profile, brand (voice, tone, words to use and avoid), forbidden topics, the chosen product, and up to 40 ready media items (favourites first; videos first for video formats) unless the media preference is "never".
- **Prompt-injection defence:** all business data is passed inside XML-style blocks that the system prompt declares to be data, not instructions; a closing tag inside user text is stripped so it can't end its block early.
- **No invented facts:** the model is told to state only facts present in the profile, product or brief (no prices, discounts, awards or quotes it wasn't given).
- **Validation after generation:** each platform's caption is cut to its limit, hashtags are cleaned (no `#`, no duplicates) and capped per platform, pillar must be a known value, and a `media_id` is accepted **only if it was one of the items offered**, so a model can't attach arbitrary files.
- **Warnings** (never blocking; approval is the gate): words to avoid, forbidden topics, over-long captions, video formats without a video, no media when the business prefers its own.

Platform rules (`rules.py`) also decide which formats each platform accepts (for example YouTube takes Shorts and video only); unsupported combinations are rejected with `422 unsupported_format`.

## Workflow

```
generate ─► generating ─► ready ──► awaiting_approval ──► approved ──► scheduled
                   └─► failed         ▲        │ reject            │ schedule / unschedule
                                      └── rejected ◄───────────────┘
```

- **Approve** works from ready, awaiting approval or rejected (editors, admins and owners; viewers are read-only).
- **Editing** an approved or scheduled post sends it back to *awaiting approval* and holds its schedule, when the workspace requires approval. A **redraft** of a post that was in the approval queue returns there.
- **Without approval** (Business and Agency, when the owner turns approval off): *send* goes straight to approved or scheduled.
- **Schedules** are one row per platform at the same instant: `pending` until approved, `queued` once approved. Times must be at least 5 minutes and at most a year ahead, and timezone-aware; the UI edits them in the **workspace** time zone, not the browser's.
- **Versions:** every edit, redraft and restore first snapshots the post (`content_versions`). Restoring creates a new version, so nothing is lost.
- **Nothing is published yet.** Approved posts wait in the queue until the Phase 5 publisher and social connections exist; the editor says so, and no code path in Phase 3 marks content as published.

## API

All under `/api/v1/workspaces/{workspace_id}`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/usage` | Allowances used and remaining this period, and the active AI provider |
| GET | `/content?status=&platform=&start=&end=&unscheduled=&q=&limit=` | List; `start`/`end` returns posts scheduled in that window (calendar) |
| POST | `/content/generate` | Start an AI draft (`202`, status `generating`) |
| POST | `/content` | Create a post by hand |
| GET / PATCH / DELETE | `/content/{id}` | Read, edit (title, hook, per-platform copy, media, script, slides), delete |
| POST | `/content/{id}/regenerate` | Redraft, with an optional instruction |
| POST | `/content/{id}/submit`, `/approve`, `/reject` | Approval workflow |
| PUT / DELETE | `/content/{id}/schedule` | Schedule or reschedule; remove from the calendar |
| POST | `/content/{id}/duplicate` | Copy as a new draft |
| GET | `/content/{id}/versions` | History |
| POST | `/content/{id}/versions/{n}/restore` | Restore a version |

## Screens

- **Create post** (`/content/new`): draft with AI or write it yourself; format, platforms (unsupported ones disabled), goal, product, media from the library, optional schedule; shows the monthly allowance and a notice when the offline test writer is active.
- **Post editor** (`/content/{id}`): hook, per-platform caption, hashtags and CTA with live limits, media, script or slides, a preview card, warnings, approve / send / reject / schedule / redraft / duplicate / history / delete.
- **Content** (`/content`): tabs for needs approval, approved and scheduled, drafts, rejected or failed; search.
- **Calendar** (`/calendar`): month and week views in the workspace time zone, platform filter, drag a post to another day (time of day is kept), drag unscheduled posts in (10:00).
