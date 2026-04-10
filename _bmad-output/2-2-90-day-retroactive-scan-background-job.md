# Story 2.2: 90-Day Retroactive Scan Background Job

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a new founder who just connected Stripe,
I want SafeNet to automatically scan my last 90 days of payment failures in the background,
so that my dashboard is populated with actionable failure data within minutes of onboarding.

## Acceptance Criteria

**AC1 — Scan Task Queueing:**
- **Given** a new Stripe Connect authorization
- **When** OAuth callback fires and creates a new account
- **Then** Celery background task `scan_retroactive_failures` is queued immediately for that account (FR2)

**AC2 — Failure Classification:**
- **Given** retroactive scan task runs
- **When** it processes each failed payment intent
- **Then** it classifies failure by Stripe decline code using `DECLINE_RULES` via `get_rule()` (FR7)
- **And** creates `SubscriberFailure` record with: `payment_intent_id`, `decline_code`, `amount_cents`, `subscriber_email`, `payment_method_country`, `created_at`, `account_id`
- **And** zero raw card data stored — only Stripe event metadata (NFR-S3)

**AC3 — Rate Limit Handling:**
- **Given** Stripe API rate limit hit during scan
- **When** task receives rate limit error
- **Then** it retries with exponential backoff — scan never hard-fails due to temporary throttling (NFR-P4)

**AC4 — Completion & Dashboard Population:**
- **Given** retroactive scan completes
- **When** task finishes
- **Then** first scan data visible in dashboard within 5 minutes post-OAuth (NFR-P3)
- **And** dashboard UI never blocked — scan runs entirely in background (NFR-P2)

**AC5 — Hourly Polling Job:**
- **Given** hourly polling job `poll_new_failures` registered with Celery beat
- **When** it runs every 60 minutes (±5 min tolerance)
- **Then** it detects new payment failures since last poll for each account (FR6)
- **And** if polling cycle missed, operator alert fires within 90 minutes (NFR-R1)
- **And** rate limit errors trigger automatic retry — no cycle abandoned due to throttling (NFR-P4)

## Tasks / Subtasks

- [x] Task 1: Create `Subscriber` and `SubscriberFailure` models + migration (AC: 2)
  - [x] 1.1: Create `backend/core/models/subscriber.py` with `Subscriber` model extending `TenantScopedModel` — fields: `stripe_customer_id` (unique per account), `email`, `status` (default `"active"`, choices from `state_machine.py` constants)
  - [x] 1.2: Create `SubscriberFailure` model in same file — fields: `subscriber` (FK), `account` (FK via `TenantScopedModel`), `payment_intent_id` (CharField, unique), `decline_code` (CharField), `amount_cents` (IntegerField), `payment_method_country` (CharField, nullable), `failure_created_at` (DateTimeField — Stripe's timestamp, not Django's `auto_now_add`), `classified_action` (CharField — result of `get_rule()`)
  - [x] 1.3: Register models in `backend/core/models/__init__.py`
  - [x] 1.4: Run `makemigrations` + `migrate`

- [x] Task 2: Implement `scan_retroactive_failures` Celery task (AC: 1, 2, 3, 4)
  - [x] 2.1: Create `backend/core/tasks/scanner.py` with `@app.task(bind=True, max_retries=5, default_retry_delay=60)` — accepts `account_id` as argument
  - [x] 2.2: Load `StripeConnection` for account, decrypt access token via `.access_token` property
  - [x] 2.3: Use `stripe.PaymentIntent.list()` with the connected account's access token, `created[gte]` = 90 days ago, `status` filter for failed intents — paginate with `auto_paging_iter()` for all results
  - [x] 2.4: For each failed payment intent: extract `decline_code` from `last_payment_error.decline_code`, `amount` (already in cents), customer email from `charges.data[0].billing_details.email` or customer object, `payment_method_country` from `charges.data[0].payment_method_details.card.country`
  - [x] 2.5: Use `get_or_create` for `Subscriber` by `stripe_customer_id` + `account_id` — set email from Stripe data
  - [x] 2.6: Use `get_or_create` for `SubscriberFailure` by `payment_intent_id` (idempotent — safe for re-runs)
  - [x] 2.7: Classify via `get_rule(decline_code)` and store `classified_action` = rule `action` field
  - [x] 2.8: Handle `stripe.error.RateLimitError` with exponential backoff: `self.retry(exc=exc, countdown=2 ** self.request.retries * 30)`
  - [x] 2.9: Write audit event on completion: `action="retroactive_scan_completed"`, `actor="engine"`, `outcome="success"`, metadata with counts
  - [x] 2.10: Write audit event on failure: `action="retroactive_scan_failed"`, `outcome="failed"`, metadata with error details

- [x] Task 3: Trigger scan from OAuth callback (AC: 1)
  - [x] 3.1: In `backend/core/views/stripe.py` `stripe_connect_callback()`, after new account creation (inside the `else` branch where `existing_connection` is falsy), call `scan_retroactive_failures.delay(account.id)`
  - [x] 3.2: Do NOT trigger scan for reconnections (existing accounts) — only on first-time OAuth

- [x] Task 4: Implement `poll_new_failures` Celery task (AC: 5)
  - [x] 4.1: Create `backend/core/tasks/polling.py` with `@app.task(bind=True)` — no arguments, iterates all active accounts
  - [x] 4.2: For each account with a `StripeConnection`, fetch failed payment intents `created[gte]` = last poll time (store as `last_polled_at` on Account or use Redis key `poll:last_run:{account_id}`)
  - [x] 4.3: Reuse same classification + `get_or_create` logic as scanner (extract to shared helper in `backend/core/services/failure_ingestion.py` to avoid duplication)
  - [x] 4.4: Handle rate limits with same exponential backoff pattern
  - [x] 4.5: Log polling completion via audit event

- [x] Task 5: Update Celery beat schedule (AC: 5)
  - [x] 5.1: In `backend/safenet_backend/celery.py`, rename existing `poll_failed_payments` schedule entry to point to `core.tasks.polling.poll_new_failures`
  - [x] 5.2: Keep 3600-second interval (hourly)
  - [x] 5.3: Update the stub `poll_failed_payments` in `core/tasks/__init__.py` — either remove or redirect to new task

- [x] Task 6: Missed-cycle operator alert (AC: 5)
  - [x] 6.1: In `poll_new_failures`, before processing, check elapsed time since last successful poll (Redis key or model timestamp)
  - [x] 6.2: If gap > 90 minutes, log a `DeadLetterLog` entry or a high-severity audit event: `action="polling_cycle_missed"`, `actor="engine"`, `outcome="alert"`, metadata with gap duration
  - [x] 6.3: Continue processing even if alert fires (alert is informational, not blocking)

- [x] Task 7: Write tests (AC: all)
  - [x] 7.1: Create `backend/core/tests/test_tasks/` directory with `__init__.py`
  - [x] 7.2: Create `test_scanner.py` — test scan task creates `Subscriber` + `SubscriberFailure` records from mocked Stripe data, test idempotency (re-run doesn't duplicate), test rate limit retry, test audit event on completion
  - [x] 7.3: Create `test_polling.py` — test poll detects new failures, test missed-cycle alert, test rate limit handling
  - [x] 7.4: Create `backend/core/tests/test_models/test_subscriber.py` — test model constraints, test `TenantScopedModel` inheritance, test `payment_intent_id` uniqueness
  - [x] 7.5: Update `backend/core/tests/test_api/test_stripe.py` — add test that OAuth callback triggers `scan_retroactive_failures.delay()` for new accounts, verify it does NOT trigger for reconnections

## Dev Notes

### Critical Architecture Constraints

- **Tenant Isolation:** Both `Subscriber` and `SubscriberFailure` MUST extend `TenantScopedModel` (from `core/models/base.py`). All queries must use `.for_account(account_id)`.
- **Token Access:** Decrypt Stripe tokens via `stripe_connection.access_token` property — NEVER access `_encrypted_access_token` directly.
- **Audit Trail:** Use `write_audit_event()` from `core/services/audit.py` for all logging. Never create `AuditLog` inline.
- **Decline Rules:** Import `get_rule()` from `core/engine/rules.py` — do NOT reimplement classification logic. The function never raises `KeyError` (falls through to `_default`).
- **Monetary Values:** Store as integer cents (`amount_cents`), never float/decimal.
- **API Fields:** All snake_case — no camelCase transformation.
- **Idempotency:** Use `get_or_create` keyed on `payment_intent_id` for `SubscriberFailure` — the scan MUST be safe to re-run without duplicating records.

### Stripe API Usage

- **Authentication:** Use the connected account's decrypted access token, NOT the platform's secret key. Pass via `stripe.api_key` parameter or `stripe.PaymentIntent.list(api_key=access_token)`.
- **Pagination:** Use `auto_paging_iter()` to handle large result sets — do NOT manually paginate with `starting_after`.
- **Filtering:** `stripe.PaymentIntent.list(created={"gte": int(ninety_days_ago.timestamp())})` — Stripe expects Unix timestamps for date filters.
- **Failed Intents:** Filter by checking `payment_intent.status` — look for `"requires_payment_method"` status (this is what Stripe uses for declined payments, NOT a `"failed"` status).
- **Decline Code Location:** `payment_intent.last_payment_error.decline_code` — may be `None` for non-card failures; use `"_default"` rule in that case.
- **Customer Email:** Try `charges.data[0].billing_details.email` first, fall back to fetching customer object if needed.
- **Country:** `charges.data[0].payment_method_details.card.country` — nullable, store as-is.
- **Rate Limits:** Stripe returns HTTP 429 — the `stripe` Python library raises `stripe.error.RateLimitError`. Use Celery's built-in retry with exponential backoff.

### Shared Ingestion Logic (DRY)

Both `scan_retroactive_failures` and `poll_new_failures` classify failures identically. Extract shared logic into `backend/core/services/failure_ingestion.py`:

```python
def ingest_failed_payment(account, payment_intent) -> tuple[Subscriber, SubscriberFailure, bool]:
    """
    Process a single failed payment intent into Subscriber + SubscriberFailure records.
    Returns (subscriber, failure, created) — `created` is False if already existed.
    """
```

This prevents the #1 LLM mistake: duplicating classification logic across tasks.

### Existing Code to Modify

| File | Change |
|------|--------|
| `backend/core/views/stripe.py` | Add `scan_retroactive_failures.delay(account.id)` after new account creation in `stripe_connect_callback()` — line ~70, inside the `else` block |
| `backend/safenet_backend/celery.py` | Update beat schedule task path from `core.tasks.poll_failed_payments` to `core.tasks.polling.poll_new_failures` |
| `backend/core/tasks/__init__.py` | Remove or update the `poll_failed_payments` stub |
| `backend/core/models/__init__.py` | Add imports for `Subscriber`, `SubscriberFailure` |

### New Files to Create

| File | Purpose |
|------|---------|
| `backend/core/models/subscriber.py` | `Subscriber` + `SubscriberFailure` models |
| `backend/core/tasks/scanner.py` | `scan_retroactive_failures` Celery task |
| `backend/core/tasks/polling.py` | `poll_new_failures` Celery task |
| `backend/core/services/failure_ingestion.py` | Shared failure processing logic |
| `backend/core/tests/test_tasks/__init__.py` | Test package |
| `backend/core/tests/test_tasks/test_scanner.py` | Scanner task tests |
| `backend/core/tests/test_tasks/test_polling.py` | Polling task tests |
| `backend/core/tests/test_models/test_subscriber.py` | Model tests |

### Testing Standards

- **Framework:** pytest + pytest-django (already configured in `pytest.ini`)
- **Database:** Use `@pytest.mark.django_db` for all tests touching models
- **Fixtures:** Extend `conftest.py` with `subscriber`, `stripe_connection` fixtures
- **Stripe Mocking:** Use `unittest.mock.patch("stripe.PaymentIntent.list")` — return mock objects matching Stripe's API shape
- **Celery Testing:** Use `CELERY_ALWAYS_EAGER=True` in test settings OR call task function directly (`.apply()` or function call) — do NOT test actual async execution
- **Assertions:** Verify record counts, field values, audit events created, and idempotency

### Previous Story Intelligence (Story 2.1)

Key patterns established in Story 2.1 that MUST be followed:
- **Atomic transactions** for multi-model creation (`transaction.atomic()`)
- **CSRF state tokens** stored in Redis cache with 10-min TTL
- **Audit events** written for every significant action
- **Property-based encryption** on StripeConnection — use `.access_token`, never raw field
- **`get_or_create` pattern** for User to handle reconnections — apply same pattern for Subscriber
- **Test structure:** `test_api/` subdirectory, pytest fixtures from `conftest.py`

### Git Intelligence

Recent commits show:
- Story-driven development with comprehensive commit messages
- Backend tasks directory already scaffolded with stub
- Celery beat schedule already in place (just needs task path update)
- All engine modules (rules, compliance, payday, state_machine) are production-ready pure Python

### Project Structure Notes

- All new models go in `backend/core/models/` as separate files (pattern: `account.py`, `audit.py`, `base.py` → `subscriber.py`)
- All new tasks go in `backend/core/tasks/` as separate files (pattern: `__init__.py` has stubs → `scanner.py`, `polling.py`)
- All new services go in `backend/core/services/` (pattern: `stripe_client.py`, `encryption.py`, `audit.py` → `failure_ingestion.py`)
- Tests mirror source structure: `tests/test_tasks/`, `tests/test_models/`, `tests/test_api/`

### References

- [Source: _bmad-output/epics.md — Epic 2, Story 2.2]
- [Source: _bmad-output/architecture.md — Core Subsystems, Project Structure, API Design]
- [Source: _bmad-output/prd.md — FR2, FR6, FR7, FR34, NFR-S3, NFR-P2, NFR-P3, NFR-P4, NFR-R1]
- [Source: backend/core/engine/rules.py — DECLINE_RULES, get_rule()]
- [Source: backend/core/models/base.py — TenantScopedModel, TenantManager]
- [Source: backend/core/views/stripe.py — stripe_connect_callback()]
- [Source: backend/safenet_backend/celery.py — beat_schedule config]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- pytest-django was listed in pyproject.toml but not installed; ran `poetry install` to resolve
- Existing Stripe callback tests failed because `scan_retroactive_failures.delay()` tried to connect to Redis — fixed by adding autouse mock fixture in TestStripeConnectCallback
- Rate limit retry tests initially expected `celery.exceptions.Retry` but `self.retry()` re-raises the original exception outside a worker context — fixed to expect `stripe.error.RateLimitError`
- Existing `test_celery_beat_schedule_has_hourly_poll` assertion updated to match new task path

### Completion Notes List
- Created `Subscriber` and `SubscriberFailure` models extending `TenantScopedModel` with UniqueConstraint on (stripe_customer_id, account)
- Implemented `scan_retroactive_failures` Celery task with 90-day lookback, rate limit retry, and audit events
- Implemented `poll_new_failures` Celery task with Redis-based last-poll tracking, missed-cycle alerts, and rate limit retry
- Extracted shared `ingest_failed_payment()` into `failure_ingestion.py` service to DRY classification logic
- Integrated scan trigger into OAuth callback (new accounts only, not reconnections)
- Updated Celery beat schedule to use new `poll_new_failures` task path
- All 135 tests pass with zero regressions

### File List

**New files:**
- `backend/core/models/subscriber.py` — Subscriber + SubscriberFailure models
- `backend/core/tasks/scanner.py` — scan_retroactive_failures Celery task
- `backend/core/tasks/polling.py` — poll_new_failures Celery task
- `backend/core/services/failure_ingestion.py` — shared failure ingestion logic
- `backend/core/migrations/0003_add_subscriber_and_subscriber_failure.py` — migration
- `backend/core/tests/test_tasks/__init__.py` — test package
- `backend/core/tests/test_tasks/test_scanner.py` — scanner task tests (7 tests)
- `backend/core/tests/test_tasks/test_polling.py` — polling task tests (6 tests)
- `backend/core/tests/test_models/__init__.py` — test package
- `backend/core/tests/test_models/test_subscriber.py` — model tests (9 tests)

**Modified files:**
- `backend/core/models/__init__.py` — added Subscriber, SubscriberFailure imports
- `backend/core/views/stripe.py` — added scan_retroactive_failures.delay() trigger after new account creation
- `backend/safenet_backend/celery.py` — updated beat schedule task path to core.tasks.polling.poll_new_failures
- `backend/core/tasks/__init__.py` — replaced stub with imports from scanner.py and polling.py
- `backend/core/tests/test_api/test_stripe.py` — added scan trigger tests + autouse mock fixture
- `backend/core/tests/test_celery.py` — updated beat schedule assertion to new task path

### Review Findings

- [x] [Review][Decision] Signal creates duplicate Account, breaking all new registrations — fixed: use `user.account` from signal, update tier/trial fields
- [x] [Review][Decision] Polling rate limit on one account aborts all remaining accounts — fixed: split into per-account subtasks (`poll_account_failures`)
- [x] [Review][Patch] `scan_retroactive_failures.delay()` called inside `transaction.atomic()` — fixed: moved after atomic block
- [x] [Review][Patch] Single bad payment intent aborts entire retroactive scan — fixed: per-intent try/except with logging
- [x] [Review][Patch] Cache TTL expiration suppresses missed-cycle alert — fixed: increased to 48hr TTL
- [x] [Review][Patch] `except IntegrityError` too narrow — fixed: widened to `except Exception`
- [x] [Review][Patch] Completion audit event in `poll_new_failures` missing `account` parameter — fixed: per-account audit events in subtask
- [x] [Review][Defer] `Subscriber.email` stores unvalidated strings from Stripe — deferred, pre-existing pattern
- [x] [Review][Defer] No `db_index` on `SubscriberFailure.failure_created_at` — deferred, performance optimization
- [x] [Review][Defer] `get_rule()` crashes on `None` input — deferred, pre-existing in rules engine

### Change Log
- 2026-04-10: Story 2.2 implementation complete — all 7 tasks implemented with 135 tests passing (22 new tests added)
- 2026-04-10: Code review completed — 2 decision-needed, 5 patch, 3 deferred, 8 dismissed. All 7 findings fixed, 137 tests passing.
- 2026-04-10: Bonus fix: `stripe.error.OAuthError` replaced with `stripe.error.StripeError` (OAuthError removed in stripe v15)
