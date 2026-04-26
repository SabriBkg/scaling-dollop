# Story 3.2: Autopilot Recovery Engine — Rule Execution & 4-State Status Machine

Status: done

## Story

As a founder on Autopilot,
I want SafeNet to automatically process every failed payment using the correct recovery rule and track each subscriber's status through the 4-state machine,
so that recovery happens without my involvement and every outcome is auditable.

## Acceptance Criteria

1. **Rule engine dispatch on new failure** — Given a new `SubscriberFailure` detected by the polling job, when the rule engine processes it via `get_recovery_action(decline_code, ...)`, then the correct action is applied per `DECLINE_RULES` (`retry_only`, `notify_only`, `retry_notify`, `fraud_flag`, `no_action`) and the subscriber's initial status is set to `active` via `django-fsm` (FR10, FR16).

2. **Payday-aware retry scheduling** — Given an `insufficient_funds` failure in Autopilot mode, when the retry scheduler runs, then the retry is queued within a 24-hour window after the 1st or 15th of the month (whichever comes next) and the retry cap of 3 attempts is enforced (FR11, FR12).

3. **Geo-compliance override** — Given a `geo_block=True` rule for a payment from an EU/UK country, when the engine processes the failure, then no retry is queued (action overridden to `notify_only`) and the override is recorded in the audit log (FR13).

4. **Successful recovery transition** — Given a retry attempt succeeds (Stripe confirms payment), when the engine processes the success, then the subscriber transitions `active → recovered` via FSM and a post-transition signal writes an audit event: `{action: "status_recovered", actor: "engine", outcome: "success"}` (FR17, NFR-R3).

5. **Retry cap exhaustion → passive churn** — Given the retry cap is exhausted with no recovery, when the engine processes the final failed attempt, then the subscriber transitions `active → passive_churn` and the audit log records the transition with final decline code and attempt count (FR18).

6. **Fraud flagging** — Given a `fraudulent` decline code, when the engine classifies the failure, then the subscriber is immediately set to `fraud_flagged`, all further actions are stopped, and the audit log records: `{action: "status_fraud_flagged", actor: "engine", outcome: "success", metadata: {decline_code: "fraudulent"}}` (FR19).

7. **Subscription cancellation detection** — Given a subscriber's Stripe subscription transitions to `cancelled`, `unpaid`, `paused`, or `cancel_at_period_end`, when the polling job detects this state, then all recovery actions stop and the subscriber transitions to `passive_churn` with the specific reason recorded (FR46).

8. **Dead letter on unhandled exception** — Given a Celery task for retry execution fails with an unhandled exception, when the exception is caught, then it is written to `DeadLetterLog` with task name, account ID, and error string, and the failure is surfaced for operator review (NFR-R5, NFR-R3).

## Tasks / Subtasks

- [x] **Task 1: Add django-fsm transitions to Subscriber model** (AC: 1, 4, 5, 6)
  - [x] 1.1 Add `django_fsm.FSMField` to replace plain `CharField` for `status` on `Subscriber`
  - [x] 1.2 Create migration (likely `0007_*`) — must handle existing rows (all currently `active`)
  - [x] 1.3 Implement FSM transition methods: `recover()` (active→recovered), `mark_passive_churn()` (active→passive_churn), `mark_fraud_flagged()` (active→fraud_flagged)
  - [x] 1.4 Add `django-fsm` transition guards to prevent invalid transitions (e.g., recovered→active)
  - [x] 1.5 Wire post-transition signal to write audit events via `write_audit_event()`

- [x] **Task 2: Create `DeadLetterLog` model** (AC: 8)
  - [x] 2.1 Create `core/models/dead_letter.py` with `DeadLetterLog(TenantScopedModel)`: task_name, account_id, error, created_at
  - [x] 2.2 Add migration
  - [x] 2.3 Register in `core/models/__init__.py`

- [x] **Task 3: Add retry tracking fields to `SubscriberFailure`** (AC: 2, 5)
  - [x] 3.1 Add `retry_count` (IntegerField, default=0), `last_retry_at` (DateTimeField, nullable), `next_retry_at` (DateTimeField, nullable) to `SubscriberFailure`
  - [x] 3.2 Add migration

- [x] **Task 4: Create recovery execution service** (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] 4.1 Create `core/services/recovery.py` — orchestrator that takes a `SubscriberFailure` and the `RecoveryDecision` and executes the correct action
  - [x] 4.2 Implement `execute_recovery_action(failure, decision, account)`:
    - `fraud_flag` → immediately transition subscriber to `fraud_flagged`
    - `no_action` → audit log only, no retry queued
    - `notify_only` → queue notification task (stub for Epic 4, log audit event now)
    - `retry_notify` → schedule retry via `schedule_retry()`, queue notification stub
  - [x] 4.3 Implement `schedule_retry(failure, decision)`:
    - Check retry_count < retry_cap, else transition to `passive_churn`
    - If payday_aware: use `next_payday_retry_window()` to set `next_retry_at`
    - If not payday_aware: set `next_retry_at` to now + configurable delay (e.g., 1 hour)
    - Write audit event for scheduling
  - [x] 4.4 Implement `process_retry_result(failure, success: bool)`:
    - On success: transition subscriber to `recovered`, clear `next_retry_at`
    - On failure: increment `retry_count`, schedule next retry or transition to `passive_churn`

- [x] **Task 5: Create retry execution Celery task** (AC: 2, 4, 5, 8)
  - [x] 5.1 Create `core/tasks/retry.py` with `execute_retry(failure_id)` task
  - [x] 5.2 Implement Stripe retry via `stripe.PaymentIntent.confirm()` using account's access token
  - [x] 5.3 Process result through `process_retry_result()`
  - [x] 5.4 Implement dead-letter logging on unhandled exceptions per mandatory Celery task pattern
  - [x] 5.5 Register with Celery beat for periodic retry execution (scan `next_retry_at <= now`)

- [x] **Task 6: Create retry dispatcher task** (AC: 2)
  - [x] 6.1 Create `execute_pending_retries()` periodic task — queries failures where `next_retry_at <= now` and subscriber status is `active`
  - [x] 6.2 Dispatch individual `execute_retry.delay(failure_id)` for each
  - [x] 6.3 Register with Celery beat (run every 15 minutes)

- [x] **Task 7: Wire polling task to trigger recovery processing** (AC: 1, 3)
  - [x] 7.1 After `ingest_failed_payment()` in `poll_account_failures`, check if account is Autopilot mode (`account.engine_mode == "autopilot"`)
  - [x] 7.2 If Autopilot: call `get_recovery_action()` then `execute_recovery_action()` for each new failure
  - [x] 7.3 If Supervised: skip execution (actions will be queued for review in Story 3.4)
  - [x] 7.4 Add geo-compliance override audit logging

- [x] **Task 8: Add subscription status detection to polling** (AC: 7)
  - [x] 8.1 During polling, check each subscriber's Stripe subscription status
  - [x] 8.2 If subscription is `cancelled`, `unpaid`, `paused`, or `cancel_at_period_end`: transition subscriber to `passive_churn` with reason metadata
  - [x] 8.3 Stop all pending retries for that subscriber (clear `next_retry_at`)

- [x] **Task 9: Backend tests** (AC: all)
  - [x] 9.1 Test FSM transitions: valid paths (active→recovered, active→passive_churn, active→fraud_flagged) and invalid paths (recovered→active raises `TransitionNotAllowed`)
  - [x] 9.2 Test post-transition signal writes audit events
  - [x] 9.3 Test recovery service: each action type (retry_notify, notify_only, fraud_flag, no_action) produces correct behavior
  - [x] 9.4 Test payday-aware scheduling: retry scheduled within correct window
  - [x] 9.5 Test retry cap enforcement: transition to passive_churn when exhausted
  - [x] 9.6 Test geo-compliance override: EU/UK payment → notify_only, non-EU → original action
  - [x] 9.7 Test retry execution task: success → recovered, failure → retry_count incremented
  - [x] 9.8 Test dead-letter logging on task exception
  - [x] 9.9 Test subscription cancellation detection → passive_churn transition
  - [x] 9.10 Test fraud flagging stops all further actions
  - [x] 9.11 Test polling integration: Autopilot accounts trigger recovery, Supervised accounts skip

## Dev Notes

### Existing Code to Reuse (DO NOT Reinvent)

- **Rule engine**: `core/engine/processor.py` → `get_recovery_action()` returns `RecoveryDecision` — already fully implemented and tested
- **Compliance**: `core/engine/compliance.py` → `get_compliant_action()` handles EU/UK geo-blocking — already implemented
- **Payday scheduling**: `core/engine/payday.py` → `next_payday_retry_window()` — already implemented
- **State constants**: `core/engine/state_machine.py` — `STATUS_*` and `ACTION_*` constants exist
- **Failure ingestion**: `core/services/failure_ingestion.py` → `ingest_failed_payment()` — already classifies action
- **Audit service**: `core/services/audit.py` → `write_audit_event()` — single write path, already used everywhere
- **Tier service**: `core/services/tier.py` → `is_engine_active()` checks tier + DPA + mode

### Architecture Constraints

- **Engine isolation**: `core/engine/` must contain ZERO Django imports. Recovery orchestration logic goes in `core/services/recovery.py` (not in engine/)
- **Tenant scoping**: All new models inherit `TenantScopedModel`. All queries use `.for_account(account_id)`
- **Celery task pattern**: All tasks must use `bind=True`, implement dead-letter on unhandled exceptions, log START/COMPLETE/FAILED
- **Audit trail**: Every engine action (retry scheduled, retry fired, status change, retry cancelled) → `write_audit_event()`. Never inline
- **API envelope**: Any new endpoints must return `{data: ...}` or `{error: ...}`. Monetary values as integer cents. Dates as ISO 8601
- **FSM library**: Use `django-fsm` 3.0.1 (already in pyproject.toml). Transitions are decorated methods with guards. `TransitionNotAllowed` on invalid transitions — never silently ignored

### django-fsm Implementation Pattern

```python
from django_fsm import FSMField, transition

class Subscriber(TenantScopedModel):
    status = FSMField(default=STATUS_ACTIVE, choices=[(s, s) for s in ALL_STATUSES])

    @transition(field=status, source=STATUS_ACTIVE, target=STATUS_RECOVERED)
    def recover(self):
        pass  # post-transition signal handles audit logging

    @transition(field=status, source=STATUS_ACTIVE, target=STATUS_PASSIVE_CHURN)
    def mark_passive_churn(self):
        pass

    @transition(field=status, source=STATUS_ACTIVE, target=STATUS_FRAUD_FLAGGED)
    def mark_fraud_flagged(self):
        pass
```

Post-transition signal (from architecture):
```python
from django_fsm.signals import post_transition

@receiver(post_transition, sender=Subscriber)
def on_status_transition(sender, instance, name, source, target, **kwargs):
    write_audit_event(
        subscriber=str(instance.id),
        actor="engine",
        action=f"status_{target}",
        outcome="success",
        metadata={"from": source, "to": target},
        account=instance.account,
    )
```

### Stripe Retry Pattern

Use `stripe.PaymentIntent.confirm()` with the account's access token (from `StripeConnection.access_token`). The PaymentIntent ID is stored in `SubscriberFailure.payment_intent_id`.

```python
stripe.PaymentIntent.confirm(
    failure.payment_intent_id,
    api_key=connection.access_token,
)
```

Check result: if status becomes `succeeded` → recovery success. If still `requires_payment_method` → retry failed.

### Known Deferred Issues to Address

From `deferred-work.md`:
- **`is_within_payday_window` timezone bug** (Story 1.3 deferred): checks `dt.day` without UTC conversion. Fix in this story since payday scheduling is now wired to production use. Convert to UTC before checking day.
- **`get_rule()` crashes on None** (Story 2.2 deferred): protected by caller defaulting to `_default`, but fix the function contract since recovery service will call it directly.
- **`stripe.error.RateLimitError` pre-v15 API** (Story 2.5 deferred): `polling.py:120` uses pre-v15 exception path. Fix when touching polling task to wire recovery processing.

### File Structure

New files:
- `backend/core/models/dead_letter.py` — DeadLetterLog model
- `backend/core/services/recovery.py` — Recovery execution orchestrator
- `backend/core/tasks/retry.py` — Retry execution + dispatcher tasks
- `backend/core/tests/test_engine/test_fsm.py` — FSM transition tests
- `backend/core/tests/test_services/test_recovery.py` — Recovery service tests
- `backend/core/tests/test_tasks/test_retry.py` — Retry task tests

Modified files:
- `backend/core/models/subscriber.py` — Add FSM transitions, retry tracking fields
- `backend/core/models/__init__.py` — Register DeadLetterLog
- `backend/core/engine/state_machine.py` — May need signal wiring helpers
- `backend/core/tasks/polling.py` — Wire recovery processing for Autopilot accounts
- `backend/core/tasks/__init__.py` — Register new tasks
- `backend/core/engine/payday.py` — Fix `is_within_payday_window` timezone bug

### Testing Standards

- **Pure engine tests**: No `@pytest.mark.django_db` for processor, rules, compliance, payday tests (already established pattern)
- **FSM tests**: Need `@pytest.mark.django_db` since they hit the ORM
- **Service tests**: Need `@pytest.mark.django_db` — test recovery orchestration with real DB
- **Task tests**: Mock Stripe API calls, use real DB for model state
- **Test the signal**: Verify post-transition signal fires `write_audit_event()` correctly
- **Test invalid transitions**: Verify `TransitionNotAllowed` raised on e.g., `recovered.mark_fraud_flagged()`

### Previous Story Intelligence (3.1)

Story 3.1 established:
- `Account.engine_mode` field (choices: `autopilot`, `supervised`, nullable)
- `Account.dpa_accepted_at` field for DPA gate
- `is_engine_active(account)` in tier service checks: tier Mid/Pro + DPA accepted + engine_mode set
- `set_engine_mode` endpoint with `select_for_update()` concurrency pattern
- Dashboard cache invalidation: `cache.delete(f"dashboard_summary_{account.id}")` on mode changes
- Audit events use metadata patterns like `{"mode": mode, "first_activation": True}`

### Data Flow (End-to-End)

```
celery beat (hourly) →
  tasks/polling.py:poll_new_failures() →
  tasks/polling.py:poll_account_failures(account_id) →
    stripe.PaymentIntent.list() (fetch failures) →
    services/failure_ingestion.py:ingest_failed_payment() →
    [NEW] check account.engine_mode == "autopilot" →
    [NEW] engine/processor.py:get_recovery_action() →
    [NEW] services/recovery.py:execute_recovery_action() →
      fraud_flag → subscriber.mark_fraud_flagged() → audit
      retry_notify → services/recovery.py:schedule_retry() → set next_retry_at → audit
      notify_only → audit (notification stub for Epic 4)
      no_action → audit

celery beat (every 15 min) →
  [NEW] tasks/retry.py:execute_pending_retries() →
    query SubscriberFailure where next_retry_at <= now, subscriber.status == active →
    tasks/retry.py:execute_retry.delay(failure_id) →
      stripe.PaymentIntent.confirm() →
      services/recovery.py:process_retry_result() →
        success → subscriber.recover() → audit
        failure → increment retry_count → schedule_retry() or mark_passive_churn() → audit
```

### References

- [Source: _bmad-output/epics.md — Epic 3, Story 3.2]
- [Source: _bmad-output/architecture.md — Decline-code Rule Engine, State Machine, Celery Task Structure, Integration Points]
- [Source: _bmad-output/ux-design-specification.md — Status Badge Variants, Attention Bar]
- [Source: _bmad-output/3-1-dpa-acceptance-engine-mode-selection-flow.md — Previous story patterns]
- [Source: _bmad-output/deferred-work.md — Payday timezone bug, get_rule None crash, Stripe v15 exceptions]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- Fixed pre-existing `is_within_payday_window` timezone bug (deferred from Story 1.3)
- Fixed `get_rule()` crash on None input (deferred from Story 2.2)
- Fixed `stripe.error.RateLimitError` pre-v15 exception path (deferred from Story 2.5) — replaced with `stripe.StripeError`
- Billing webhook tests (8) are pre-existing failures due to missing STRIPE_WEBHOOK_SECRET env var — not related to this story

### Completion Notes List
- Task 1: Replaced CharField with django-fsm FSMField on Subscriber.status. Added 3 transition methods (recover, mark_passive_churn, mark_fraud_flagged) with guards. Wired post_transition signal for audit logging. Migration 0007.
- Task 2: Created DeadLetterLog model for dead-letter logging on task exceptions. Migration 0008.
- Task 3: Added retry_count, last_retry_at, next_retry_at fields to SubscriberFailure. Migration 0009.
- Task 4: Created recovery execution service with execute_recovery_action(), schedule_retry(), process_retry_result(). Handles all 4 action types, payday-aware scheduling, retry cap enforcement.
- Task 5: Created execute_retry Celery task with Stripe PaymentIntent.confirm(), dead-letter logging, and result processing.
- Task 6: Created execute_pending_retries dispatcher task (every 15 min via Celery beat). Queries due retries and dispatches individual tasks.
- Task 7: Wired polling task to trigger recovery for Autopilot accounts. Added geo-compliance override audit logging. Supervised accounts skip (Story 3.4).
- Task 8: Added subscription cancellation detection during polling. Transitions to passive_churn and clears pending retries on cancelled/unpaid/paused/cancel_at_period_end.
- Task 9: 42 new tests across 4 test files covering all ACs: FSM transitions (valid + invalid), audit signals, recovery service actions, payday scheduling, retry cap, geo-compliance, retry tasks, dead-letter, subscription cancellation, polling integration.

### Review Findings

#### Decision Resolved
- [x] [Review][Decision→Patch] **Concurrent retry execution race condition** — resolved: add `select_for_update()` in `execute_retry`
- [x] [Review][Decision→Patch] **`TransitionNotAllowed` never caught** — resolved: catch and log as audit event, skip transition
- [x] [Review][Decision→Defer] **Stripe `PaymentIntent.confirm` on `requires_payment_method` status** — deferred: known limitation, needs dedicated story to attach updated payment method before confirm
- [x] [Review][Decision→Patch] **Transient Stripe errors consumed as business retry failures** — resolved: distinguish retryable vs permanent Stripe errors

#### Patches
- [x] [Review][Patch] Retry dispatcher beat schedule is 86400s (daily) instead of 900s (15 min) [celery.py:25] — FIXED
- [x] [Review][Patch] `execute_retry` imports `transaction` but never uses it — wrap confirm+process in `transaction.atomic()` [retry.py] — FIXED
- [x] [Review][Patch] `_detect_card_updates` exclude filter logic inverted — replaced with `filter(next_retry_at__isnull=False)` [polling.py] — FIXED
- [x] [Review][Patch] `_queue_immediate_retry` picks most recent failure without checking retry cap or active status [polling.py] — FIXED: added `subscriber__status` and `next_retry_at` filters
- [x] [Review][Patch] `excluded_from_automation` not checked in `_process_autopilot_recovery` [polling.py] — FIXED
- [x] [Review][Patch] ~~Off-by-one in retry cap~~ — DISMISSED: verified correct (3 attempts for cap=3, test confirms)
- [x] [Review][Patch] `execute_pending_retries` missing dead-letter handling [retry.py] — FIXED: added try/except with error logging (DeadLetterLog requires account FK, so using logger.error)
- [x] [Review][Patch] `process_retry_result` failure path doesn't clear stale `next_retry_at` [recovery.py] — FIXED: `schedule_retry` now clears `next_retry_at` on cap exhaustion
- [x] [Review][Patch] Add `select_for_update()` in `execute_retry` [retry.py] — FIXED
- [x] [Review][Patch] Catch `TransitionNotAllowed` in recovery service [recovery.py] — FIXED: added `_safe_transition()` helper with audit logging
- [x] [Review][Patch] Distinguish retryable vs permanent Stripe errors in `execute_retry` [retry.py] — FIXED: `RateLimitError`/`APIConnectionError` use `self.retry()`, others burn count

#### Deferred (pre-existing)
- [x] [Review][Defer] N+1 Stripe API calls in `_check_subscription_cancellations` and `_detect_card_updates` — no batching or rate limiting [polling.py] — deferred, pre-existing
- [x] [Review][Defer] Cache loss causes `_process_unqueued_failures` to potentially re-dispatch recovery actions [polling.py] — deferred, pre-existing
- [x] [Review][Defer] `SubscriberFailure.amount_cents` is `IntegerField` — potential overflow for high-value JPY/KRW transactions [subscriber.py:72] — deferred, pre-existing
- [x] [Review][Defer] Stripe `PaymentIntent.confirm` cannot succeed on `requires_payment_method` without attaching updated payment method first — needs dedicated story [retry.py:54] — deferred, decision from review

### Change Log
- 2026-04-14: Story 3.2 implementation complete — recovery engine, FSM, retry system, polling integration, subscription detection. 3 deferred bugs fixed.

### File List
New files:
- backend/core/models/dead_letter.py
- backend/core/services/recovery.py
- backend/core/tasks/retry.py
- backend/core/migrations/0007_subscriber_fsm_status.py
- backend/core/migrations/0008_add_dead_letter_log.py
- backend/core/migrations/0009_add_retry_tracking_fields.py
- backend/core/tests/test_engine/test_fsm.py
- backend/core/tests/test_services/test_recovery.py
- backend/core/tests/test_tasks/test_retry.py
- backend/core/tests/test_tasks/test_polling_recovery.py

Modified files:
- backend/core/models/subscriber.py — FSMField, transitions, signal, retry tracking fields
- backend/core/models/__init__.py — Register DeadLetterLog
- backend/core/engine/payday.py — Fixed is_within_payday_window timezone bug
- backend/core/engine/rules.py — Fixed get_rule() None crash
- backend/core/tasks/polling.py — Wired recovery processing, subscription cancellation detection, fixed Stripe exception
- backend/core/tasks/__init__.py — Register new tasks
- backend/safenet_backend/celery.py — Added retry-dispatcher-15min beat schedule
