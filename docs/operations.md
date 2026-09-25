# Notifications, agent activity, admin and security

**Status:** implemented in Phase 8. Covered by `backend/tests/test_operations.py` (4 tests), `backend/tests/test_guards.py` (2 structural tests) and the browser test `frontend/e2e/phase8.py` (10 checks).

## Notifications (`app/notifications/`)

| Event | Who | Email by default |
| --- | --- | --- |
| Post waiting for approval, at the workspace's reminder times (24 h, 6 h, 1 h before) | owners, admins, editors | yes |
| Post missed its time because it wasn't approved | owners, admins, editors | yes |
| Post failed to publish | owners, admins, editors | yes |
| Account needs reconnecting | owners, admins | yes |
| Allowance at 80 % and 100 % | owners, admins | yes |
| Post published; new insight | owners, admins, editors | no (in-app) |

- Every notification has a dedupe key, so a reminder, failure or warning is never sent twice.
- Notifications are created inside the transaction of the event. Emails go out from a once-a-minute job that only sees committed rows, so a rolled-back change never emails anyone.
- Each person controls in-app and email per type and per business in **Settings → Notifications**; turning both off means nothing is created.
- The bell in the app header shows unread notifications across all the person's businesses, polls every minute, and links to the post or page concerned.

## Agent activity (`app/agents/activity.py`)

Real work writes a run with plain-language steps: AI drafts (Content agent: what it read, which photo it chose, what it wrote, cost), publishing (Publishing agent: result per platform) and nightly analysis (Analytics agent). Each run records its limits (20 steps, 15 minutes, $1.00) and cost. **Agent activity** shows the timeline with the steps expandable; the dashboard shows the latest runs.

## Admin (`/admin`, `app/api/v1/admin.py`)

Superusers only (`python -m scripts.set_admin email --by "Name"` grants it; `--revoke` removes it; both audited).

- **Overview:** users, sign-ups this week, businesses, plans, MRR (active Paddle subscriptions only), AI calls and cost over 30 days, publications and failures this week.
- **Customers:** search, plan, status, last sign-in; suspend with a reason (their sessions end immediately and they can't sign in), restore.
- **Audit log:** the latest security, billing, content and admin events with actor and IP.

## Security posture

- **Authentication:** Argon2id, rotating refresh sessions with reuse detection, httpOnly cookies, CSRF double-submit, lockouts and rate limits ([auth.md](auth.md)).
- **Authorisation:** workspace access resolves membership on every request (non-members get 404); every write endpoint checks the caller's role. `tests/test_guards.py` walks all routes and fails if a new write endpoint forgets its role check, or an admin endpoint forgets the superuser check.
- **Rate limits** on expensive work: AI drafts 30/min, images 10/min, video builds 5/min, uploads 120/min, insight refresh 6/min (per IP), on top of the monthly allowances.
- **Content Security Policy** from Next.js: scripts from self and Paddle only, no `eval` in production, no framing (`frame-ancestors 'none'`), no plugins, forms to self, plus `nosniff`, `DENY` framing, a strict referrer policy and HSTS in production. `connect-src` allows `https:` because uploads go straight to a deployment-specific storage host; `upgrade-insecure-requests` applies when `NEXT_PUBLIC_APP_URL` is HTTPS.
- **Secrets at rest:** social tokens Fernet-encrypted; session, reset and verification tokens stored as keyed hashes.
- **Uploads:** type checked from bytes, sizes enforced by storage, files served with a sandboxing CSP.
- **AI:** business data passed as delimited data (prompt-injection containment), model output validated, and a model can only attach media it was offered.
