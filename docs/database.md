# Database

PostgreSQL 16 with the `pgvector` extension. Schema is managed by Alembic (`backend/alembic/versions/`); the initial migration creates 34 tables and ~114 indexes; Phase 3 adds `content_versions` and `ai_response_cache` (36 tables); later phases add columns (`publications.provider_state`, `marketing_insights.key`, `marketing_memory.pinned`) and the `assembled` media source (a CHECK-constraint migration). `alembic check` reports no drift between models and migrations.

## Conventions

- UUID primary keys, generated in Python (`uuid4`) with `gen_random_uuid()` as the database default for raw SQL inserts.
- `created_at` / `updated_at` on every table (timezone-aware); `deleted_at` soft delete where records must survive for audit or billing.
- Enumerations are `VARCHAR` with named `CHECK` constraints (easier to evolve than native Postgres enums).
- Flexible attributes use `JSONB` with explicit defaults; tag arrays use GIN indexes.
- Constraint names follow a naming convention so migrations are deterministic.
- Emails are unique case-insensitively among non-deleted users (partial unique index on `lower(email)`).

## Tables

| Area | Tables |
| --- | --- |
| Identity | `users`, `sessions`, `email_verification_tokens`, `password_reset_tokens` |
| Workspaces | `workspaces`, `workspace_members` |
| Business | `business_profiles`, `brands`, `products`, `product_media` |
| Media | `media_folders`, `media_assets` |
| Social | `social_accounts`, `social_account_tokens` |
| Content | `contents`, `content_variants`, `content_media`, `content_schedules`, `content_versions`, `publications` |
| Analytics | `platform_metrics`, `metric_snapshots` |
| Intelligence | `marketing_insights`, `marketing_memory`, `experiments`, `experiment_variants`, `research_items` |
| Agents | `agent_runs`, `agent_steps` |
| Notifications | `notifications`, `notification_preferences` |
| Billing and usage | `subscriptions`, `billing_events`, `ai_usage`, `ai_response_cache` |
| Audit | `audit_logs` |

## Design decisions worth knowing

- **Tokens are never stored in plain text.** Session refresh tokens, verification and reset tokens are stored as HMAC-SHA256 hashes keyed by `SESSION_SECRET`. Social access and refresh tokens are Fernet-encrypted (`ENCRYPTION_KEYS`, rotatable) in `social_account_tokens`.
- **Refresh rotation keeps the previous hash** (`previous_refresh_token_hash`, `rotated_at`) for a short grace window, so two tabs refreshing at once don't log the user out, while reuse after the window revokes the session.
- **Publishing is idempotent.** `publications.idempotency_key` is unique (content, platform, account, scheduled time) and inserted with `ON CONFLICT DO NOTHING`. `publications.provider_state` keeps the platform's upload id between attempts so retries never start a second upload.
- **Metrics can be absent.** Metric columns on `platform_metrics` are nullable and `available_metrics` lists what the platform actually reported. `NULL` means "not available from this platform", never zero.
- **Insights carry evidence.** `marketing_insights` stores `sample_size`, `period_start`, `period_end`, `confidence` and an `evidence` JSON payload. The dashboard hides insights below `MIN_INSIGHT_SAMPLE` (8).
- **Memory is retrieved, not trained.** `marketing_memory.embedding` is `vector(1536)` (configurable via `AI_EMBEDDING_DIMENSIONS` before first migration) with an HNSW cosine index.
- **Media status lifecycle:** `pending_upload` → `processing` → `ready`, or `failed` / `quarantined` (content didn't match its type). Pending rows older than 24 h are purged nightly. See [media-storage.md](media-storage.md).
- **Generated media is never paid for twice.** `media_assets.generation_fingerprint` (hash of model, prompt and parameters) and `checksum_sha256` are indexed for deduplication.
- **Agent runs copy their limits** (`max_steps`, `max_runtime_seconds`, `max_cost_usd`, `max_retries`) at creation, so later config changes don't alter a run in flight.
- **Billing events are idempotent.** `billing_events.paddle_event_id` is unique; `subscriptions.last_event_occurred_at` rejects out-of-order webhooks.
- **AI usage has a reservation lifecycle:** reserved → committed or refunded, with cost and cache-hit flags.

## Commands

```bash
cd backend
alembic upgrade head                       # apply
alembic downgrade base                     # drop everything (dev only)
alembic revision --autogenerate -m "..."   # new migration, then review it by hand
alembic check                              # fail if models and migrations differ
```
