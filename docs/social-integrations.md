# Social accounts and publishing

**Status:** implemented in Phase 5. Covered by `backend/tests/test_social.py` (7 tests) and the browser test `frontend/e2e/phase5.py` (10 checks). Not yet run against the real Meta, TikTok or Google APIs: see "Before launch".

## Rule zero

Never fake a connection, a publish or a metric. A publication is `published` only when the platform returned an id for the post. Providers without app credentials show as "Not available on this server yet"; there is no mock connection in the product.

## Providers (`backend/app/social/adapters/`)

| Provider | Platforms | Connect | Publishes | Notes |
| --- | --- | --- | --- | --- |
| Meta | Instagram (professional accounts), Facebook Pages | Facebook Login, long-lived user token, then Page tokens | IG: photo, carousel (2–10), Reel, Story via containers; FB: photo, video, text | IG accepts JPEG photos only. Page tokens don't expire; an invalid one asks for reconnect. |
| TikTok | TikTok | OAuth v2 with PKCE | Video (`PULL_FROM_URL`) | Unaudited apps may only post privately (`SELF_ONLY`); the adapter uses the most public level the account currently offers and records it. |
| YouTube | YouTube | Google OAuth (`youtube.upload`) with PKCE, offline access | Shorts and videos via resumable upload, streamed from storage | Unverified Google apps' uploads stay private. Uses `GOOGLE_CLIENT_ID/SECRET`. |

All adapters implement one protocol (`app/social/base.py`): `authorize_url`, `connect`, `refresh`, `validate`, `publish`. Errors are classified as **retryable** (outages, rate limits), **processing** (platform still processing a video), **needs reauth** (expired or revoked access) or permanent.

## Connecting (`app/social/service.py`)

1. `POST /workspaces/{id}/social/{provider}/connect` (owners and admins) returns the provider's authorize URL and sets a signed, 10-minute `cf_oauth_social` cookie scoped to the callback path, holding the workspace, user, PKCE verifier and a nonce (the OAuth `state`).
2. The provider redirects to `GET /api/v1/social/callback/{provider}`; state and cookie must match and be fresh.
3. Every eligible account on that login is saved (e.g. each Page and its Instagram account), **within the plan's account limit** counted across all workspaces the owner has (Free 1, Starter 3, Business 8, Agency 25). Reconnecting an existing account always works and refreshes its tokens. Accounts beyond the limit are reported as skipped.
4. Tokens are Fernet-encrypted (`ENCRYPTION_KEYS`) in `social_account_tokens`. Disconnecting deletes the token row.
5. An hourly job refreshes tokens expiring within 24 hours; a refresh that fails with an auth error marks the account `expired`, which shows on the dashboard as "renew connection".

Redirect URIs to register with each provider: `{APP_URL}/api/v1/social/callback/meta`, `/tiktok`, `/youtube`.

## Publishing engine (`app/social/publisher.py`)

Every minute the worker runs `enqueue_due_publications`:

- **Approved and due** schedules become `publications` rows. The idempotency key (content, platform, account, scheduled time) is unique, and rows are inserted with `ON CONFLICT DO NOTHING`, so overlapping scheduler runs can't create two publications.
- **Not approved and due** schedules become `approval_overdue` and are never published.
- A platform with **no connected account** gets a failed publication saying which account to connect.
- **Stuck publishing** rows (a worker died mid-call more than 15 minutes ago) are marked `unknown_outcome` and ask a person to check the platform before retrying, rather than risking a duplicate post.

`publish_publication` then, per publication:

1. Checks the account, decrypts tokens and runs the adapter's format validation. **All of this happens before the point of no return.**
2. Marks the row `publishing` and commits, then calls the platform.
3. Success: stores the post id and URL, marks `published`, rolls the post's status up (`published` when every platform succeeded, `failed` if any failed, `publishing` otherwise).
4. Processing (videos): polls every 30 s for up to 30 minutes. The provider's upload id (IG container, TikTok publish id) is kept in `publications.provider_state`, so polling and retries resume the same upload instead of creating another.
5. Retryable errors back off 1 min, 5 min, 15 min, 1 h, 3 h, then fail.
6. Auth errors mark the account `expired` and fail the publication.

**Manual retry** (`POST /workspaces/{id}/publications/{pid}/retry`) goes to the **same account** the post was meant for, never quietly to a different Page or channel; if that account is disconnected or expired, it asks you to reconnect it first.

## Media must be reachable by the platforms

Instagram, Facebook and TikTok fetch media from our URLs. With `STORAGE_PROVIDER=s3` those are presigned URLs the platforms can fetch. With local storage the URLs point at this server, which platforms can't reach in development; the Social accounts page says so.

## Screens

- **Settings → Social accounts:** each provider with its connected accounts, health, errors and disconnect; the plan's account limit; the result of the last connection.
- **Post editor:** a warning when a post targets a platform with no connected account; "Publishes automatically on …" once scheduled; a Publishing panel per platform (waiting, retrying at, published with a link, failed with the reason and a Retry button). Published posts are read-only (duplicate to make a new version). The editor watches a post from two minutes before its time until it's out.

## Testing locally

Set `META_CLIENT_ID`, `META_CLIENT_SECRET`, `META_DIALOG_BASE_URL=http://127.0.0.1:8098` and `META_GRAPH_BASE_URL=http://127.0.0.1:8098` for **both the API and the worker**, then run `python3 frontend/e2e/phase5.py`. It serves a stand-in for Meta's login dialog and Graph API, connects through the real OAuth callback, lets the worker's minute job publish, and checks the stored permalink.

## Before launch

- Create the Meta, TikTok and Google apps, register the redirect URIs, and run one real connect and publish per platform in their test modes.
- Meta: App Review for `instagram_content_publish`, `pages_manage_posts` and related permissions. TikTok: Content Posting API audit (until then posts are private). Google: OAuth verification for `youtube.upload` (until then uploads are private).
- Use S3-compatible storage so platforms can fetch media.
