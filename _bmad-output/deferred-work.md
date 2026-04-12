# Deferred Work

## Deferred from: code review of story-1-1 (2026-04-06)

- STRIPE_TOKEN_KEY placeholder is an invalid Fernet key — `cp .env.example .env` gives a non-functional encryption key. Must generate a real key before Story 1.2 (Stripe token encryption).
- `redis` package unpinned in `requirements.txt` — all other packages are pinned. A major version bump could break Celery/Django cache integration silently.
- `production.py` re-creates `environ.Env()` instead of reusing the instance from `base.py` — shadows the base `env`, no `read_env()` called. Works because Railway injects real env vars, but inconsistent with the base pattern.

## Deferred from: code review of story-1-2 (2026-04-07)

- `AuditLog.save()` immutability guard is bypassable via `QuerySet.update()` and `bulk_update()` — Django ORM bulk operations skip `save()`. Requires DB-level REVOKE on UPDATE/DELETE for the app PostgreSQL role, or a custom manager that overrides `update()`/`delete()`.
- `isRefreshing` and `failedQueue` in `frontend/src/lib/api.ts` are module-level globals that persist across SSR requests in Next.js server context. If the axios instance is ever used server-side, one user's refresh flow could bleed into another's. Fix when adding SSR data fetching.

## Deferred from: code review of story-1-3 (2026-04-08)

- `is_within_payday_window` checks only `dt.day in (1, 15)` without converting to UTC — inconsistent with `next_payday_retry_window` which produces UTC-aware windows. Not used in production yet; fix when wiring payday scheduling in Story 3.2.
- `get_compliant_action` uses an allowlist of non-retry actions (`fraud_flag`, `notify_only`, `no_action`). If new action types are added, they could bypass geo-blocking. The action set is fixed by current spec; revisit if action types expand.

## Deferred from: code review of story-2-1 (2026-04-10)

- Unauthenticated `initiate_stripe_connect` endpoint creates a cache entry per POST with no rate limiting — attacker can flood Redis with `stripe_oauth_state:*` keys. Needs rate limiting middleware or throttle class.
- Dockerfile runs as root with no `USER` directive and installs Poetry via `curl | python3` without checksum verification. Address when hardening container security.
- Missing env vars (`STRIPE_REDIRECT_URI`, `STRIPE_CLIENT_ID`, `STRIPE_SECRET_KEY`) cause unhandled `ImproperlyConfigured` crash. Add startup validation or graceful error handling.

## Deferred from: code review of story-2-2 (2026-04-10)

- `Subscriber.email` is `EmailField` but `failure_ingestion.py` stores unvalidated strings from Stripe via `get_or_create` (bypasses Django field validators). Malformed emails could cause downstream failures in email-sending features.
- No `db_index` on `SubscriberFailure.failure_created_at` — date-range queries will full-scan the table. Add index when dashboard query patterns are established.
- `get_rule()` in `core/engine/rules.py` crashes on `None` input with `AttributeError` — currently protected by caller defaulting to `"_default"`, but function contract is misleading. Fix when touching the rules engine.

## Deferred from: code review of story-2-3 (2026-04-10)

- `useAccount` query fires without auth gate (`enabled` flag) — fires 401 on unauthenticated page loads within dashboard layout. Consider gating with `enabled: !!isAuthenticated`.
- Dashboard layout flash of unauthenticated shell before middleware redirect — no client-side auth guard in `(dashboard)/layout.tsx`. Relies on middleware + axios 401 interceptor.
- `useAccount` error state unhandled in consumers — failed account fetch silently degrades WorkspaceIdentity (shows "Workspace" with no owner). No error UI or retry prompt.
- UserMenu shows "?" avatar before auth hydration completes — no skeleton/loading state for null `user` in authStore.
- Mobile navigation inaccessible below `md:` breakpoint — nav tabs hidden with no hamburger or fallback. Mobile is read-only MVP; needs a dedicated mobile nav story.

## Deferred from: code review of story-2-4 (2026-04-11)

- `toLocaleString()` locale-dependent number formatting — `total_failures.toLocaleString()` renders differently per browser locale (e.g., "1.000" in German vs "1,000" in English). Pre-existing pattern across the frontend.
- `recovery_rate` can theoretically exceed 100% — no model-level constraint prevents `recovered_count > total_subscribers` from data inconsistency. Needs database-level validation when touching the recovery engine.
- Frontend `recovery_action` TypeScript union vs backend string field — DB `classified_action` allows any string up to 50 chars but TS type restricts to 4 known values. If new actions are added to `DECLINE_RULES`, frontend silently falls back to wrong indicator color.

## Deferred from: code review of story-2-1b (2026-04-12)

- `ScopedRateThrottle` in `DEFAULT_THROTTLE_CLASSES` silently passes endpoints without a `throttle_scope` — `AllowAny` endpoints like `initiate_stripe_connect` and `stripe_connect_callback` have no rate limiting. An attacker could flood the cache with state tokens or exhaust DB connections. [backend/safenet_backend/settings/base.py:103]
- `stripe.error.StripeError` may not exist in Stripe SDK v15 — `backend/core/views/stripe.py:93` catches `stripe.error.StripeError` but Stripe v15 moved exceptions to `stripe.StripeError`. Falls through to generic exception handler. [backend/core/views/stripe.py:93]
