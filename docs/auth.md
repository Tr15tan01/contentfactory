# Authentication

Custom authentication in FastAPI (no Auth.js). Everything below is implemented and covered by `backend/tests/test_auth.py`, `test_authorization.py` and `test_security.py`, plus the browser smoke test.

## Credentials

- Passwords are hashed with **Argon2id** (`argon2-cffi`), rehashed on login when parameters change. A dummy hash is verified for unknown emails so response time doesn't reveal whether an account exists.
- Rules: at least `PASSWORD_MIN_LENGTH` (10) and at most 128 characters, not overly repetitive (4+ distinct characters), and not containing the email's local part. Errors are returned per field. A breached-password check (k-anonymity lookup) is a candidate for Phase 8 hardening.

## Sessions and cookies

| Cookie | Contents | Flags | Path |
| --- | --- | --- | --- |
| `cf_access` | JWT (HS256), 15 min, `sid` claim, issuer and audience checked | httpOnly, SameSite=Lax, Secure in prod | `/` |
| `cf_refresh` | Opaque 256-bit token, 30 days | httpOnly, SameSite=Strict, Secure in prod | `/api/v1/auth` |
| `cf_csrf` | Signed random token | readable by JS, SameSite=Lax | `/` |
| `cf_signed_in` | `1` (routing hint only, grants nothing) | readable, SameSite=Lax | `/` |

- Every authenticated request loads user **and** session in one query, so revoking a session takes effect immediately even for an unexpired access token.
- **Refresh rotation:** each refresh issues a new refresh token and stores the previous hash. A stale token used within `REFRESH_REUSE_GRACE_SECONDS` (15 s) returns `409 refresh_superseded` (another tab already rotated; the client retries). Reuse after the window is treated as theft: the session is revoked and `auth.refresh_reuse` is audited.
- The frontend API client refreshes once per burst of 401s (single-flight) and retries the original request.

## CSRF

Double-submit: every unsafe request must send `X-CSRF-Token` equal to the signed `cf_csrf` cookie, and a present `Origin` must be `APP_URL` or listed in `CORS_ORIGINS`. Paddle webhooks and health checks are exempt (they're authenticated by signature or read-only). SameSite cookies are defence in depth, not the only barrier.

## Abuse protection

- Login: per-IP and per-email counters in Redis, plus a database lockout after `LOGIN_MAX_ATTEMPTS` (5) failures for `LOGIN_LOCKOUT_MINUTES` (15). Unknown emails are rate-limited identically.
- Rate limits on register, refresh, resend verification, forgot and reset password, and the contact form (`429` with `Retry-After`).
- Client IP is taken from `X-Forwarded-For` honouring only `TRUSTED_PROXY_COUNT` hops (the Next.js proxy is one).

## Flows

| Flow | Endpoint(s) | Notes |
| --- | --- | --- |
| Register | `POST /auth/register` | With verification on, the response is identical whether or not the email exists (existing owners get an "you already have an account" email). With it off, `409 email_taken`. Creates a workspace (owner membership) and a Free subscription. |
| Verify email | `POST /auth/verify-email` | Single-use token, 48 h; signs the user in. |
| Login | `POST /auth/login` | `email_not_verified`, `account_suspended`, `invalid_credentials`, `429` |
| Refresh / logout | `POST /auth/refresh`, `POST /auth/logout` | Logout revokes the server session. |
| Forgot / reset | `POST /auth/password/forgot`, `/reset` | Silent for unknown emails; 30 min single-use token; revokes all sessions; marks the email verified; sends a "password changed" email. |
| Change password | `POST /auth/password/change` | Revokes other sessions. Google-only users can set a first password without a current one. |
| Sessions | `GET /auth/sessions`, `DELETE /auth/sessions/{id}`, `POST /auth/sessions/revoke-others` | Other users' sessions return 404. |
| Delete account | `POST /auth/account/delete` | Password, or typed email for Google-only users. Anonymises the email, soft-deletes owned workspaces, revokes sessions. |
| Google | `GET /auth/google/start`, `/callback` | See below. |

## Feature switches

| Variable | Effect |
| --- | --- |
| `AUTH_REQUIRE_EMAIL_VERIFICATION=1/0` | Require a confirmed email before first login. |
| `AUTH_GOOGLE_ENABLED=1/0` | Show "Continue with Google" and enable the OAuth routes (404 when off). |

The frontend reads both from `GET /auth/config`, so no rebuild is needed to switch them.

## Google sign-in

Authorization code flow with **PKCE** and a signed, short-lived state cookie scoped to `/api/v1/auth/google`. The redirect URI is `{APP_URL}/api/v1/auth/google/callback`; register it in Google Cloud Console. After sign-in, `next` is only honoured for same-site relative paths.

Account linking: a verified Google email links to an existing account with that email. If the existing account is a **password account that never verified its email**, the password is cleared before linking, which prevents an attacker from pre-registering someone's email and waiting for them to sign in with Google.

## Authorisation

- Workspace routes resolve membership through `get_workspace_context`; non-members get **404**, not 403.
- Roles: `owner`, `admin`, `editor`, `viewer`. Mutations call `ctx.require_role(...)`.
- Superusers (`is_superuser`) are reserved for the admin area (Phase 8) and gated by `require_superuser`.
- Security-relevant events are written to `audit_logs` in the same transaction as the change.
