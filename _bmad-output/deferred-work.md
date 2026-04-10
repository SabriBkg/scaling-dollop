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
