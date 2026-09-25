# Billing and quotas

**Status:** implemented in Phase 4. Covered by `backend/tests/test_billing.py` (6 tests) and the browser test `frontend/e2e/phase4.py` (13 checks).

## Plans

`backend/app/billing/plans.py` is the single source of truth. `frontend/lib/plans.ts` mirrors it for marketing pages, and `backend/tests/test_plans_mirror.py` fails if the two drift.

| | Free | Starter | Business | Agency |
| --- | --- | --- | --- | --- |
| Price / month | $0 | $19 | $49 | $99 |
| Businesses | 1 | 1 | 3 | 10 |
| Social accounts | 1 | 3 | 8 | 25 |
| AI content generations | 10 | 60 | 250 | 700 |
| Image generations | 10 | 40 | 150 | 400 |
| AI video credits | 2 | 5 | 20 | 50 |
| Scheduled posts | 10 | 100 | 500 | 2,000 |
| Autopilot, auto-publish, research agent | – | – | ✓ | ✓ |
| Experiments | – | basic | full | advanced |
| Priority processing | – | – | – | ✓ |

Nothing is unlimited. Quotas reset monthly on the subscription's billing anniversary (calendar month on Free).

## Paddle is the source of truth

A paid plan changes **only** when a verified Paddle webhook says so. The checkout redirect, a button press or a plan-change API call never changes the plan by itself; the Billing page shows "Confirming with Paddle" and updates when the webhook lands.

**Checkout.** `POST /billing/checkout {plan}` returns what Paddle.js needs: price id, client token, environment, the customer's email and `custom_data = {user_id, sig}`. The signature (HMAC with `SESSION_SECRET`) proves we issued that user reference, so a forged `custom_data` can't attach a subscription to someone else's account. The Billing page loads Paddle.js v2 on demand and opens the overlay checkout. Existing subscribers are sent to plan changes instead (`409 already_subscribed`).

**Webhook** `POST /api/v1/billing/webhooks/paddle` (CSRF-exempt, authenticated by signature):

1. Verify `Paddle-Signature` (`ts=…;h1=…`, HMAC-SHA256 over `"{ts}:{raw body}"` with `PADDLE_WEBHOOK_SECRET`), rejecting timestamps more than 5 minutes off. Several `h1` values are accepted so the secret can be rotated. Failures return 401 and write nothing.
2. Insert into `billing_events` with `ON CONFLICT DO NOTHING` on the Paddle event id. A repeated delivery returns `{"status": "duplicate"}` and changes nothing.
3. Match the subscription by Paddle subscription id, or for a new one by the signed `custom_data`. Unmatched events are stored with a `processing_error`.
4. Ignore events older than `subscriptions.last_event_occurred_at` (`stale`): Paddle doesn't guarantee order.
5. Map the price id to a plan. An unknown price is recorded and the plan is left unchanged.
6. Apply status, plan, price, period, scheduled change and cancellation in the same transaction, audit it, and if the effective plan went down, apply downgrade constraints.
7. If processing crashes, the transaction rolls back and the endpoint returns 500, so Paddle retries later.

Subscribe the webhook in Paddle to at least `subscription.created`, `subscription.updated`, `subscription.activated`, `subscription.canceled`, `subscription.past_due`, `subscription.paused`, `subscription.resumed` and `subscription.trialing`. `transaction.*` events are stored for the record.

**Status rules.** `active`, `trialing` and `past_due` keep the paid plan (Paddle retries failed payments; the Billing page asks the customer to update their card). `paused` and `canceled` fall back to Free. `manual_plan_override` wins over everything.

**Plan changes.** `POST /billing/change-plan {plan}` asks Paddle to swap the subscription's price with `prorated_immediately`: an upgrade charges the prorated difference now, a downgrade credits the unused part to the next bill. Moving to Free is a cancellation. `POST /billing/cancel` cancels at the end of the period (`effective_from: next_billing_period`); `POST /billing/resume` removes the scheduled cancellation. `POST /billing/portal` returns a Paddle customer-portal link for invoices and payment methods.

**Downgrades never delete anything.** `apply_plan_constraints` turns off what the new plan doesn't include across every workspace the customer owns: publishing without approval goes back to requiring approval, and autopilot is switched off. Content, media and memory stay.

**Allowance periods.** Paid plans count AI drafts, images and video credits over the Paddle billing period (`current_billing_period`); Free counts calendar months. Scheduled posts are counted per calendar month of the scheduled date.

**Support overrides.** `python -m scripts.set_plan someone@example.com business --by "Name"` sets a plan without Paddle (and `clear` removes it). Every change is audited and applies downgrade constraints.

## Testing billing locally

No Paddle account is needed to exercise the full loop:

1. Start the API with test values: `PADDLE_API_KEY`, `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET=pdl_ntfset_e2e`, `PADDLE_{STARTER,BUSINESS,AGENCY}_PRICE_ID=pri_e2e_{starter,business,agency}` and `PADDLE_API_BASE_URL=http://127.0.0.1:8099`.
2. Run `python3 frontend/e2e/phase4.py`. It serves a stand-in for the Paddle API on port 8099 that records calls, and plays Paddle's part by sending **signed** webhooks. It checks that the plan only changes when the webhook arrives.

For a real sandbox, create the three prices in Paddle's sandbox, point a webhook at `https://<your-app>/api/v1/billing/webhooks/paddle`, and use Paddle's test cards.

## AI credit accounting

Every AI call goes through one service that writes `ai_usage`:

1. **Reserve** the estimated units before calling the provider. If the reservation would exceed the plan limit, fail with `quota_exceeded` and an upgrade prompt, without calling the provider.
2. **Commit** actual units and provider cost on success.
3. **Refund** on failure or timeout, so users are never charged for failed work.
4. **Cache:** identical requests (same operation, model and normalised input fingerprint) return the stored result with `cache_hit=true` and no charge. Generated images are deduplicated through `media_assets.generation_fingerprint`.

Images cost one allowance unit each. Built videos cost one video credit per started 30 seconds; the cost is shown before building ([ai-media.md](ai-media.md)).

## Cost control

- Per-workspace daily cost ceilings in addition to monthly quotas, and per-run `max_cost_usd` for agents.
- Fast model for classification and short copy, reasoning model only for strategy and analysis.
- Admin dashboard (Phase 8) shows provider cost per workspace and plan margin.
