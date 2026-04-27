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

## Deferred from: code review of story-2-5 (2026-04-13)

- `polling.py:120` uses pre-v15 `stripe.error.RateLimitError` — dead exception handler if SDK v15 removed this path. Rate limit errors would crash the polling task instead of retrying with backoff. Story spec says DO NOT fix in this story.
- Free-tier polling gate relies on Redis cache key `poll:last_run:{account_id}` with 48h TTL — cache eviction (memory pressure, restart) resets the gate, allowing Free accounts to poll at hourly rate instead of intended 15-day interval. Architectural decision: consider persisting last_poll_at in the database.
- Engine activation flow (DPA + mode selection) not presented after upgrade — AC4 clause 3 of Story 2-5 references this flow, but DPA UI is Story 3-1 (backlog). Wire up `engine_active` check post-upgrade when Story 3-1 is built.

## Deferred from: code review of story-3-1 (2026-04-14)

- Expired trial accounts retain Mid-tier privileges for up to 24h until daily celery beat job runs. `set_engine_mode` and `is_engine_active` don't inline-check trial expiry. Architectural decision: consider calling `check_and_degrade_trial` inline in account-mutating endpoints, or increasing celery beat frequency.
- Frontend stale cache after webhook-driven downgrade — React Query continues showing `engine_active: true`, old tier, and engine mode until next refetch (window focus or polling interval). Would need WebSocket/SSE push or shorter staleTime to mitigate.
- `STRIPE_WEBHOOK_SECRET` defaults to empty string at module level — warning logs and runtime guard added in story 2-5 review, but should be a hard startup error in production environments to prevent fail-open risk.

## Deferred from: code review of story-3-2 (2026-04-15)

- N+1 Stripe API calls in `_check_subscription_cancellations` and `_detect_card_updates` — iterates all active subscribers making individual API calls per subscriber with no batching or rate limiting. Will hit Stripe rate limits at scale.
- Cache loss causes `_process_unqueued_failures` to potentially re-dispatch recovery actions for already-processed failures. Idempotent ingestion guards new failures, but recovery actions could duplicate.
- `SubscriberFailure.amount_cents` is `IntegerField` (max ~2.1B) — potential overflow for high-value JPY/KRW transactions. Consider `BigIntegerField`.
- Stripe `PaymentIntent.confirm` on `requires_payment_method` status will always fail without first attaching the subscriber's updated payment method. Retries burn business retry counts without actually re-charging. Needs a dedicated story to fetch default PM from Customer and attach to PI before confirming.

## Deferred from: code review of story-3-3 (2026-04-24)

- N+1 Stripe API calls in `_detect_card_updates` — 1 `Customer.retrieve` per active subscriber with pending failures. Spec Task 5.3 requires batching but it was not implemented. Will hit Stripe rate limits at scale.
- N+1 Stripe API calls in `_check_subscription_cancellations` — Same N+1 pattern with `Subscription.list` per subscriber. Combined with card detection, 2+ API calls per subscriber per poll cycle.
- Race condition: fingerprint read-modify-write in `_detect_card_updates` without `select_for_update` or atomic block. Concurrent polls for the same account could cause lost fingerprint updates. Low risk since daily polls are serialized by Celery.
- `cancel_at_period_end` in `_check_subscription_cancellations` transitions subscriber to `passive_churn` while subscription is still active until period ends, prematurely stopping recovery efforts.

## Deferred from: code review of story-3-4 (2026-04-24)

- `_check_subscription_cancellations` calls `subscriber.mark_passive_churn()` directly instead of `_safe_transition()` — TransitionNotAllowed would crash the entire polling task for that account. Pre-existing; fix when touching subscription cancellation logic.
- Business logic (decision re-derivation + execution loop) lives inline in `batch_approve_actions` view instead of a service function. Violates "no business logic in views" constraint. Functional as-is; refactor when adding batch action features.
- `_safe_transition` has TOCTOU race: `method()` then `save()` without `select_for_update()`. Concurrent workers can overwrite subscriber state. Needs systemic DB-level locking pattern across all FSM transitions.
- `formatCents` in PendingActionRow.tsx hardcodes USD currency. Multi-currency support is out of scope for this story.
- `process_retry_result` checks in-memory `subscriber.status` which can be stale from concurrent transitions. `_safe_transition` catches TransitionNotAllowed, but a `refresh_from_db` pattern would be more robust.

## Deferred from: code review of story-3-5 (2026-04-25)

- Backfill / polling-catchup code duplication — `_backfill_recent_failures` (`backend/core/views/account.py`) and `_process_unqueued_failures` (`backend/core/tasks/polling.py`) are near-identical; extract to a shared service when next touching either path.
- Backfill runs synchronously inside the engine-activation HTTP request (`views/account.py:247`) — risks request timeout for accounts with many recent failures. Move to a Celery task before scaling beyond MVP account sizes.
- Backfill / polling-catchup: no `select_for_update` on failures or PendingAction creation; concurrent mode-switch + active poll could create duplicate pending actions. Race window is narrow today but should be hardened when concurrency surfaces tighten.
- `subscriber_list` view (`backend/core/views/subscribers.py`) returns all subscribers in one payload — no DRF pagination. Acceptable while account counts are small; add pagination before scale.
- `subscriber_list` view has no caching — hit on every poll (5-min refetch × every dashboard tab). Optimization, not correctness.
- `useSubscribers` hook (`frontend/src/hooks/useSubscribers.ts`) lacks `enabled`/`refetchIntervalInBackground` and has equal `staleTime`/`refetchInterval`. Polling-discipline tweak; harmonize across the hook suite later.
- Dashboard page (`frontend/src/app/(dashboard)/dashboard/page.tsx`) has no error UI and no empty-state — skeleton spins forever on API error; zero subscribers renders nothing. Address in a broader dashboard UX pass.
- `DashboardAttentionBar` silently hides on `isError` (`DashboardAttentionBar.tsx:11`). Acceptable for a non-critical bar; revisit when error UX is unified.
- Activate/mode page invalidates queries then `router.push`es immediately — brief stale-data window on navigation. Low impact.
- Polling catchup `_process_unqueued_failures` is gated only on `is_engine_active(account)`, not on `account.engine_mode in {autopilot, supervised}`. State desync between the two flags is currently prevented elsewhere; defense-in-depth would re-check.
- Backfill / polling-catchup skip non-active subscribers — failures on `recovered`/`passive_churn` subscribers never re-evaluated. Confirm intentional with PM; current scope is active-only recovery.
- Dashboard cache stale on FSM transition (5-minute TTL on `dashboard_summary_*`) — fraud_flag transitions are not invalidated proactively. 5-minute lag is acceptable per current design.
- `latest_failure` subquery in `subscribers.py:25-28` is not account-scoped — defense-in-depth only; parent queryset is already scoped via `for_account`.
- Backfill autopilot path emits no `trigger=engine_activation_backfill` audit metadata (only the supervised branch does); relies on `execute_recovery_action`'s own audit. Cross-check audit completeness in a dedicated pass.

## Deferred from: code review of story-4-1-resend-integration-branded-failure-notification-email (2026-04-25)

- `test_dead_letter_on_exhausted_retries` calls `.run.__func__` with a mock `self` instead of going through Celery's real retry path — covers the dead-letter branch but not retry semantics. Needs a Celery integration test.
- `schedule_retry` (`backend/core/services/recovery.py:153-156`) clears `next_retry_at` and saves before calling `_safe_transition`, whose return value is ignored — state and audit can drift if the FSM blocks the transition. Story 3.2 scope.
- `poll_account_failures` (`backend/core/tasks/polling.py:1085`) retries indefinitely on `RateLimitError`/`APIConnectionError`/`APIError` — no `max_retries` cap, no dead-letter, exponential backoff is unbounded. Story 3.x polling hardening.
- `pending_action_list` (`backend/core/views/actions.py:1903`) reports `len(serializer.data)` as `meta.total` instead of `actions.count()` — misreports total under pagination/filtering. Story 3.4.
- `execute_recovery_action` (`backend/core/views/actions.py:67-83`) dispatches Celery tasks inside `transaction.atomic()` — should use `transaction.on_commit` so tasks don't run against rolled-back state. Story 3.4.
- `action_ids` validation (`backend/core/views/actions.py:38-43`) accepts booleans (`isinstance(True, int)` is truthy) — `True`/`False` slip through as id=1/id=0. Minor.
- Subscriber state can go stale between queryset load and processing in batch endpoints (`backend/core/views/actions.py:72`) — `excluded_from_automation` flip not detected mid-batch. Story 3.4.
- `useEffect` selection guard in `frontend/src/app/(dashboard)/review-queue/page.tsx:2107-2117` does not differentiate "first non-empty load" from "any load" — empty → non-empty → empty → non-empty cycle won't re-select. Story 3.4.
- Rapid clicks on Exclude (`frontend/src/app/(dashboard)/review-queue/page.tsx:64-103`) can dispatch duplicate mutations — `isExcluding` not checked at handler entry. Story 3.4.
- Mid-loop failure in batch exclude (`frontend/src/app/(dashboard)/review-queue/page.tsx:78-86`) leaves subset excluded with only one toast — use `Promise.allSettled` to surface partial state. Story 3.4.
- `SAFENET_SENDING_DOMAIN` defaults to `payments.safenet.app` (`.env.example`, `settings/base.py`); if not verified in Resend every email will bounce → 3-retry → dead-letter cascade. No startup verification check. Ops/runbook concern.

## Deferred from: code review of story-4-2-tone-selector-settings-live-notification-preview (2026-04-26)

- iframe `sandbox=""` in `NotificationPreview.tsx` blocks the CTA link click — UX consideration. A user trying to verify the link destination cannot click through. Surface URL textually beneath the iframe in a follow-up if user feedback warrants it.
- `useNotificationPreview` `staleTime: 5min` does not invalidate on `complete_profile` flow — if `account.company_name` changes, the preview shows stale text for up to 5 minutes. Cross-story fix: invalidate `["notification-preview"]` from the profile-completion handler (or any future endpoint that mutates `company_name`).

## Deferred from: code review of story-4-3-final-notice-recovery-confirmation-emails (2026-04-27)

- `_record_failure` swallows all exceptions during DLL / NotificationLog writes (`backend/core/tasks/notifications.py`) — silent failures invisible to alerting. Pre-existing pattern from 4.1; address as a notifications-resilience epic.
- `customer_update_url` accepts `javascript:` and other dangerous URL schemes (`backend/core/services/email.py:223`) — `html.escape(quote=True)` does not block scheme abuse on `<a href>`. Should be validated at the account-update boundary. Pre-existing across all CTA-bearing email types.
- `resend.Emails.send` has no client-side timeout (`backend/core/services/email.py:296-300, 352-357, 402-407`) — worker stall past Celery visibility timeout causes redelivery and amplifies the duplicate-send race. Pre-existing across all three send paths.
- `NotificationLog.email_type` has no `choices=` / CHECK constraint (`backend/core/models/notification.py`) — typos silently create new categories. Pre-existing from 4.1 schema.
- `is_last_retry = (retry_count + 1) == retry_cap` uses `==`, not `>=` (`backend/core/services/recovery.py:204`) — final notice never fires if `retry_count` somehow exceeds `retry_cap`. Data-corruption edge case.
- `retry_cap` change between retries (admin edits the rule mid-flight) skews `is_last_retry` (`backend/core/services/recovery.py:204`) — final notice fires too early or never for in-flight failures. Out of scope for 4.3.
- `_safe_transition` raises non-`TransitionNotAllowed` exception (DB error) after `retry_count` is saved (`backend/core/services/recovery.py`) — `retry_count` persisted but FSM stuck. Broader DB-resilience concern.
- `NotificationLog.objects.create` raises non-`IntegrityError` after Resend already sent (`backend/core/tasks/notifications.py:113-121`) — audit divergence (sent email but no DB row). Broader DB-resilience concern.
- `resend.Emails.send` may return a dict missing `"id"` key or raise an SDK-specific exception class (`backend/core/services/email.py`) — current `dict["id"]` access and broad `except Exception` work but are SDK-contract assumptions.
