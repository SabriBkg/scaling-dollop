# Story 3.4: Supervised Mode — Pending Action Queue & Batch Approval

Status: done

## Story

As a founder in Supervised mode,
I want to review all pending recovery actions with pre-selected recommendations before they execute,
so that I stay in control of edge cases without having to configure anything from scratch.

## Acceptance Criteria

1. **Failures queued, not executed** — Given a new failure is detected for an account in Supervised mode, when the engine processes it, then the action is added to the pending queue rather than executed immediately (FR14), and the `EngineStatusIndicator` badge count increments to reflect pending reviews.

2. **Review queue displays pending actions** — Given the Supervised review queue screen, when the client opens it, then each row shows: subscriber name, plain-language decline reason, recommended action (pre-selected per decline code), and amount at risk (UX-DR16). All rows are pre-selected by default — the client reviews, not configures.

3. **Batch approval executes actions** — Given the client selects rows and clicks "Apply recommended actions", when the `POST /api/v1/actions/batch/` endpoint is called, then all selected actions are queued for execution, a toast confirms "N actions queued", and partial batch failure is surfaced with a warning toast — not silently swallowed (UX-DR8).

4. **Subscriber exclusion** — Given the client selects a subscriber and clicks "Exclude from automation", when the exclusion confirmation dialog is accepted, then that subscriber is excluded from all future automated retries and notifications, the exclusion is recorded in the audit log, and the subscriber is removed from the review queue.

5. **Zero-state** — Given the review queue is empty, when all pending actions have been processed, then the zero-state renders: "Nothing needs your eyes right now. Approved items and automated recoveries are handled." (UX-DR18).

## Tasks / Subtasks

- [x] **Task 1: Add `excluded_from_automation` field to Subscriber** (AC: 4)
  - [x] 1.1 Add `excluded_from_automation` BooleanField (default=False) to `Subscriber` model
  - [x] 1.2 Create migration (likely `0011_*`)

- [x] **Task 2: Add `pending_action` model for Supervised queue** (AC: 1, 2, 3)
  - [x] 2.1 Create `PendingAction` model in `core/models/pending_action.py` inheriting `TenantScopedModel`:
    - `subscriber` FK to Subscriber
    - `failure` FK to SubscriberFailure
    - `recommended_action` CharField (from `classified_action`)
    - `recommended_retry_cap` IntegerField
    - `recommended_payday_aware` BooleanField
    - `status` CharField: `pending` | `approved` | `excluded` (default: `pending`)
    - `created_at` DateTimeField (auto_now_add)
  - [x] 2.2 Create migration
  - [x] 2.3 Register in `core/models/__init__.py`

- [x] **Task 3: Wire Supervised mode into polling to queue actions** (AC: 1)
  - [x] 3.1 In `poll_account_failures()`, when `account.engine_mode == "supervised"` and a new failure is ingested:
    - Call `get_recovery_action()` to derive the `RecoveryDecision`
    - Create a `PendingAction` record with the recommended action details
    - Write audit event: `{action: "action_queued_supervised", metadata: {failure_id, recommended_action}}`
  - [x] 3.2 Do NOT call `execute_recovery_action()` for Supervised — that's the key difference from Autopilot
  - [x] 3.3 Exception: `fraud_flag` actions should still execute immediately even in Supervised mode (fraud must never wait for approval)

- [x] **Task 4: Backend — Pending actions list API** (AC: 2)
  - [x]4.1 Create `core/views/actions.py` with `GET /api/v1/actions/pending/` endpoint
  - [x]4.2 Create `PendingActionSerializer` in `core/serializers/actions.py`:
    - `id`, `subscriber_name` (from subscriber.email or stripe_customer_id), `decline_reason` (human label from `labels.py`), `recommended_action`, `amount_cents` (from failure.amount_cents), `created_at`, `failure_id`, `subscriber_id`
  - [x]4.3 Filter: `status=pending`, tenant-scoped, ordered by `created_at DESC`
  - [x]4.4 Response envelope: `{data: [...], meta: {total: N}}`

- [x] **Task 5: Backend — Batch action endpoint** (AC: 3)
  - [x]5.1 Create `POST /api/v1/actions/batch/` in `core/views/actions.py`
  - [x]5.2 Request body: `{action_ids: [1, 2, 3]}` — list of PendingAction IDs to approve
  - [x]5.3 For each approved action:
    - Update PendingAction status to `approved`
    - Call `execute_recovery_action(failure, decision, account)` from recovery service
    - Track successes and failures
  - [x]5.4 Response: `{data: {approved: N, failed: N, failures: [{id, error}]}}`
  - [x]5.5 Partial failure: return 200 with both counts — never 500 for partial batch failure

- [x] **Task 6: Backend — Subscriber exclusion endpoint** (AC: 4)
  - [x]6.1 Create `POST /api/v1/subscribers/{id}/exclude/` in `core/views/actions.py`
  - [x]6.2 Set `subscriber.excluded_from_automation = True`, save
  - [x]6.3 Update all pending PendingAction records for this subscriber to `status=excluded`
  - [x]6.4 Clear any `next_retry_at` on the subscriber's failures (stop pending retries)
  - [x]6.5 Write audit event: `{action: "subscriber_excluded", actor: "client"}`
  - [x]6.6 Response: `{data: {excluded: true, subscriber_id: N}}`

- [x] **Task 7: Backend — Pending count for badge** (AC: 1)
  - [x]7.1 Add `pending_action_count` to the `GET /api/v1/dashboard/summary/` response — count of PendingAction where status=pending for this account
  - [x]7.2 Update `DashboardSummarySerializer` with the new field

- [x] **Task 8: Wire URL routes** (AC: all backend)
  - [x]8.1 Add to `core/urls.py`:
    - `v1/actions/pending/` → pending action list
    - `v1/actions/batch/` → batch approval
    - `v1/subscribers/<int:subscriber_id>/exclude/` → subscriber exclusion

- [x] **Task 9: Frontend — Review queue page** (AC: 2, 5)
  - [x]9.1 Create `frontend/src/app/(dashboard)/review/page.tsx` — review queue page
  - [x]9.2 Create `usePendingActions` TanStack Query hook (`GET /api/v1/actions/pending/`)
  - [x]9.3 Render each pending action as a row: checkbox, subscriber name, plain-language decline reason (use `DeclineCodeExplainer` pattern), recommended action badge, amount at risk (formatted from cents)
  - [x]9.4 All rows pre-selected by default (checkboxes checked on load)
  - [x]9.5 Zero-state: "Nothing needs your eyes right now. Approved items and automated recoveries are handled."

- [x] **Task 10: Frontend — BatchActionToolbar component** (AC: 3, 4)
  - [x]10.1 Create `frontend/src/components/review/BatchActionToolbar.tsx`
  - [x]10.2 Anatomy: selection count ("N subscribers selected"), "Apply recommended actions" primary CTA, "Exclude from automation" ghost/destructive button, "Deselect all" link
  - [x]10.3 Slides up from bottom on row selection, sticky within viewport
  - [x]10.4 `role="toolbar"` with keyboard navigation
  - [x]10.5 Hidden when no rows selected

- [x] **Task 11: Frontend — Batch action mutation** (AC: 3)
  - [x]11.1 Create `useBatchAction` TanStack Query mutation hook (`POST /api/v1/actions/batch/`)
  - [x]11.2 On success: show success toast "N actions queued", invalidate pending actions query, clear batch selection
  - [x]11.3 On partial failure: show warning toast (amber, 6s + manual dismiss) with failure count
  - [x]11.4 On full failure: show error toast (persistent + manual dismiss)

- [x] **Task 12: Frontend — Exclusion flow** (AC: 4)
  - [x]12.1 Create `useExcludeSubscriber` TanStack Query mutation hook (`POST /api/v1/subscribers/{id}/exclude/`)
  - [x]12.2 Confirmation dialog (shadcn Dialog): "This subscriber will not receive automated retries or notifications."
  - [x]12.3 On confirm: call mutation, remove from queue, show success toast
  - [x]12.4 Invalidate pending actions query after exclusion

- [x] **Task 13: Frontend — Badge count on nav** (AC: 1)
  - [x]13.1 Use `pending_action_count` from dashboard summary to show badge on "Review Queue" nav item
  - [x]13.2 Badge only visible when count > 0 and `engine_mode === "supervised"`
  - [x]13.3 Add nav link for review queue in sidebar/navbar

- [x] **Task 14: Backend tests** (AC: all)
  - [x]14.1 Test Supervised polling: new failure creates PendingAction, does NOT execute recovery
  - [x]14.2 Test Supervised polling: fraud_flag failures still execute immediately (not queued)
  - [x]14.3 Test pending actions list: returns correct data shape with human labels
  - [x]14.4 Test batch approval: approved actions execute via recovery service
  - [x]14.5 Test batch partial failure: returns 200 with success/failure counts
  - [x]14.6 Test subscriber exclusion: sets flag, updates pending actions, clears retries, writes audit
  - [x]14.7 Test excluded subscribers: not included in future PendingAction creation
  - [x]14.8 Test pending count in dashboard summary
  - [x]14.9 Test tenant isolation: can only see/act on own pending actions

- [x] **Task 15: Frontend tests** (AC: 2, 3, 4, 5)
  - [x]15.1 Test review queue renders pending actions with correct data
  - [x]15.2 Test all rows pre-selected on load
  - [x]15.3 Test batch toolbar appears on selection, hidden on deselect-all
  - [x]15.4 Test batch approval shows success toast
  - [x]15.5 Test exclusion confirmation dialog flow
  - [x]15.6 Test zero-state renders correct message
  - [x]15.7 Test badge count on nav item

## Dev Notes

### Existing Code to Reuse (DO NOT Reinvent)

- **Recovery service**: `core/services/recovery.py` → `execute_recovery_action(failure, decision, account)` — call this for batch-approved actions. Already handles all action types with audit events
- **Rule engine**: `core/engine/processor.py` → `get_recovery_action()` — use to derive the RecoveryDecision for each failure when creating PendingAction
- **Decline labels**: `core/engine/labels.py` → `DECLINE_CODE_LABELS` — maps decline codes to plain-language strings for the review queue rows
- **Audit service**: `core/services/audit.py` → `write_audit_event()` — single write path
- **uiStore batch selection**: `frontend/src/stores/uiStore.ts` — already has `batchSelection` Set, `addToBatch()`, `removeFromBatch()`, `clearBatch()` — built for this story in Story 1.4
- **Dashboard summary hook**: `frontend/src/hooks/useDashboardSummary.ts` — add pending count field
- **Engine status hook**: `frontend/src/hooks/useEngineStatus.ts` — already derives mode from account
- **Toast component**: Use shadcn/ui `Toast` (success: 4s, warning: 6s + dismiss, error: persistent + dismiss)

### Architecture Constraints

- **API envelope**: All responses `{data: ...}` or `{error: ...}`. Never bare root objects. Monetary values as integer cents. Dates as ISO 8601
- **Tenant scoping**: All queries use `.for_account(account_id)`. PendingAction must inherit `TenantScopedModel`
- **Audit trail**: Every action → `write_audit_event()`. Batch approval, exclusion, and queueing all require audit events
- **No business logic in views**: Views validate input, call engine/service, return result
- **TypeScript snake_case**: All API response types use snake_case fields — no camelCase
- **TanStack Query for server state**: Never `useState` for data from API. Use `useQuery` for reads, `useMutation` for writes
- **Zustand for client state**: Batch selection already lives in `uiStore`

### Supervised Mode Design — Key Principle

**Marc reviews, he doesn't configure.** The review queue pre-selects all rows with the engine's recommended action. Marc's cognitive load is near-zero: scan the list, deselect anything that looks wrong, hit "Apply." The UI is a batch approval tool, not a configuration form.

### Fraud Exception in Supervised Mode

Even in Supervised mode, `fraud_flag` actions MUST execute immediately — fraud detection cannot wait for human review. When the polling job detects a fraud decline code, it should:
1. Execute `mark_fraud_flagged()` on the subscriber immediately
2. Write audit event
3. NOT create a PendingAction for this failure

All other actions (retry_notify, notify_only, no_action) get queued as PendingAction for review.

### PendingAction vs Direct Execution Flow

```
Autopilot mode:
  new failure → get_recovery_action() → execute_recovery_action() → done

Supervised mode:
  new failure → get_recovery_action() → create PendingAction(recommended_action=decision.action)
  later: Marc approves → POST /actions/batch/ → execute_recovery_action() → done
```

### Batch Approval Implementation

The `POST /api/v1/actions/batch/` endpoint should:
1. Validate all action_ids belong to the requesting account (tenant isolation)
2. For each PendingAction:
   - Re-derive the RecoveryDecision from the failure's decline code (in case rules changed)
   - Call `execute_recovery_action(failure, decision, account)`
   - Mark PendingAction as `approved`
   - Track success/failure
3. Return results with both counts

```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def batch_approve_actions(request):
    action_ids = request.data.get("action_ids", [])
    account = request.user.account

    actions = PendingAction.objects.for_account(account.id).filter(
        id__in=action_ids, status="pending"
    ).select_related("failure", "failure__subscriber")

    approved, failed, failures = 0, 0, []
    for action in actions:
        try:
            decision = get_recovery_action(
                action.failure.decline_code,
                payment_method_country=action.failure.payment_method_country,
            )
            execute_recovery_action(action.failure, decision, account)
            action.status = "approved"
            action.save(update_fields=["status"])
            approved += 1
        except Exception as exc:
            failed += 1
            failures.append({"id": action.id, "error": str(exc)})

    return Response({"data": {"approved": approved, "failed": failed, "failures": failures}})
```

### Frontend Component Structure

```
frontend/src/
  app/(dashboard)/review/page.tsx      # Review queue page
  components/review/
    BatchActionToolbar.tsx              # Sticky bottom toolbar
    PendingActionRow.tsx                # Individual row in review queue
    ExclusionDialog.tsx                 # Confirmation dialog for exclusion
  hooks/
    usePendingActions.ts                # GET /api/v1/actions/pending/
    useBatchAction.ts                   # POST /api/v1/actions/batch/ mutation
    useExcludeSubscriber.ts             # POST /api/v1/subscribers/{id}/exclude/ mutation
  types/
    actions.ts                          # PendingAction, BatchResult TypeScript interfaces
```

### TypeScript Types

```typescript
// types/actions.ts
interface PendingAction {
  id: number;
  subscriber_name: string;
  decline_reason: string;       // human-readable from labels.py
  recommended_action: string;   // retry_notify | notify_only | no_action
  amount_cents: number;
  created_at: string;           // ISO 8601
  failure_id: number;
  subscriber_id: number;
}

interface BatchResult {
  approved: number;
  failed: number;
  failures: Array<{ id: number; error: string }>;
}
```

### Toast Patterns (from UX spec)

| Type | Trigger | Duration | Icon |
|------|---------|----------|------|
| `success` | Batch approval complete | 4s | green check |
| `warning` | Partial batch failure | 6s + manual dismiss | amber warning |
| `error` | Full batch failure | Persistent + manual dismiss | red X |

### Previous Story Intelligence (3.2, 3.3)

Story 3.2 established:
- FSM transitions: `recover()`, `mark_passive_churn()`, `mark_fraud_flagged()`
- Recovery service: `execute_recovery_action()`, `schedule_retry()`, `process_retry_result()`
- Polling already checks `account.engine_mode == "autopilot"` before calling `_process_autopilot_recovery()` — add Supervised branch alongside it
- Subscription cancellation detection applies to both modes

Story 3.3 established:
- Card update detection with immediate retry dispatching
- Card update detection runs for Autopilot accounts — should also create PendingAction for Supervised accounts when card update is detected

### Data Flow

```
Supervised failure ingestion:
  poll_account_failures() →
    ingest_failed_payment() →
    check engine_mode == "supervised" →
    get_recovery_action() →
    if fraud_flag: execute immediately (bypass queue)
    else: create PendingAction(recommended_action, failure, subscriber)

Supervised batch approval:
  Frontend: POST /api/v1/actions/batch/ {action_ids: [1,2,3]} →
    for each PendingAction:
      re-derive RecoveryDecision →
      execute_recovery_action() →
      mark PendingAction approved
    return {data: {approved: N, failed: N}}

Subscriber exclusion:
  Frontend: POST /api/v1/subscribers/{id}/exclude/ →
    subscriber.excluded_from_automation = True →
    PendingAction.filter(subscriber=sub, status=pending).update(status=excluded) →
    SubscriberFailure.filter(subscriber=sub).update(next_retry_at=None) →
    write_audit_event(action="subscriber_excluded", actor="client")
```

### File Structure

New files:
- `backend/core/models/pending_action.py` — PendingAction model
- `backend/core/views/actions.py` — Pending list, batch approve, subscriber exclude endpoints
- `backend/core/serializers/actions.py` — PendingActionSerializer
- `backend/core/migrations/0011_*` — Subscriber.excluded_from_automation + PendingAction
- `backend/core/tests/test_api/test_batch.py` — Batch action API tests
- `backend/core/tests/test_tasks/test_polling_supervised.py` — Supervised polling tests
- `frontend/src/app/(dashboard)/review/page.tsx` — Review queue page
- `frontend/src/components/review/BatchActionToolbar.tsx`
- `frontend/src/components/review/PendingActionRow.tsx`
- `frontend/src/components/review/ExclusionDialog.tsx`
- `frontend/src/hooks/usePendingActions.ts`
- `frontend/src/hooks/useBatchAction.ts`
- `frontend/src/hooks/useExcludeSubscriber.ts`
- `frontend/src/types/actions.ts`
- `frontend/src/__tests__/ReviewQueuePage.test.tsx`
- `frontend/src/__tests__/BatchActionToolbar.test.tsx`

Modified files:
- `backend/core/models/subscriber.py` — Add `excluded_from_automation` field
- `backend/core/models/__init__.py` — Register PendingAction
- `backend/core/urls.py` — Add action/subscriber routes
- `backend/core/tasks/polling.py` — Add Supervised branch to create PendingAction
- `backend/core/serializers/dashboard.py` — Add `pending_action_count`
- `backend/core/views/dashboard.py` — Compute pending count
- `frontend/src/types/account.ts` — (no change needed — engine_mode already typed)
- `frontend/src/components/common/NavBar.tsx` — Add review queue link with badge

### Testing Standards

- **Backend API tests**: Use DRF `APIClient` with JWT auth, test tenant isolation
- **Serializer tests**: Verify human-readable labels in response
- **Task tests**: Mock Stripe, verify PendingAction creation for Supervised, immediate execution for fraud
- **Frontend tests**: React Testing Library + MSW for API mocking
- **Follow existing patterns**: See `test_api/test_dpa.py`, `test_api/test_engine_mode.py` for view test structure

### References

- [Source: _bmad-output/epics.md — Epic 3, Story 3.4]
- [Source: _bmad-output/architecture.md — Batch Actions Endpoint, Supervised Mode, API Patterns, Component Organization]
- [Source: _bmad-output/ux-design-specification.md — Supervised Review Queue, BatchActionToolbar, Toast Patterns, Zero-State, UX-DR8/DR16/DR18]
- [Source: _bmad-output/3-2-autopilot-recovery-engine-rule-execution-4-state-status-machine.md — Recovery service, FSM, polling integration]
- [Source: _bmad-output/3-3-card-update-detection-immediate-retry.md — Card update detection pattern]

### Review Findings

#### Decision Needed (all resolved — dismissed)
- [x] [Review][Dismissed] **D1: EngineStatusIndicator missing badge count** — NavBar badge satisfies AC1 intent
- [x] [Review][Dismissed] **D2: _detect_card_updates query semantics change** — Intentional: only failures already in retry pipeline trigger card-update detection
- [x] [Review][Dismissed] **D3: ExclusionDialog shows no subscriber identity** — Acceptable for MVP

#### Patch (fix is unambiguous)
- [x] [Review][Dismissed] **P1: schedule_retry references undefined `account` variable** — FALSE POSITIVE: `account = failure.account` already defined at line 149
- [x] [Review][Dismissed] **P2: process_retry_result references undefined `account` variable** — FALSE POSITIVE: `account = failure.account` already defined at line 210
- [x] [Review][Patch] **P3: _safe_transition return value ignored for fraud flag audit** — FIXED: audit outcome now conditional on transition result [backend/core/services/recovery.py]
- [x] [Review][Patch] **P4: batch_approve_actions has no transaction atomicity** — FIXED: wrapped each action in `transaction.atomic()` [backend/core/views/actions.py]
- [x] [Review][Patch] **P5: handleExclude fires parallel mutations without coordination** — FIXED: refactored to sequential `mutateAsync` with consolidated toast and error handling [frontend/src/app/(dashboard)/review-queue/page.tsx]
- [x] [Review][Patch] **P6: No duplicate guard on PendingAction creation** — FIXED: changed to `get_or_create` with `(failure, status=pending)` guard [backend/core/tasks/polling.py]
- [x] [Review][Patch] **P7: Exception message leaks in batch approve response** — FIXED: generic error message instead of `str(exc)` [backend/core/views/actions.py]
- [x] [Review][Patch] **P8: No per-action audit for batch approval failures** — FIXED: individual `batch_action_failed` audit event in except block [backend/core/views/actions.py]
- [x] [Review][Patch] **P9: Narrowed Stripe exception misses APIError (5xx)** — FIXED: added `stripe.APIError` to exception tuple [backend/core/tasks/polling.py]
- [x] [Review][Patch] **P10: Batch audit event always records outcome="success"** — FIXED: conditional outcome (success/partial/failed) [backend/core/views/actions.py]
- [x] [Review][Patch] **P11: Batch approve race with concurrent exclusion** — FIXED: re-checks `excluded_from_automation` inside transaction loop [backend/core/views/actions.py]
- [x] [Review][Patch] **P12: No size limit on action_ids in batch approve** — FIXED: MAX_BATCH_SIZE=100 with 400 error [backend/core/views/actions.py]
- [x] [Review][Patch] **P13: useEffect auto-selects all rows on every 60s refetch** — FIXED: `useRef` guard for initial selection only [frontend/src/app/(dashboard)/review-queue/page.tsx]
- [x] [Review][Patch] **P14: ExclusionDialog isPending not connected to mutation state** — FIXED: dedicated `isExcluding` state tracks full async flow [frontend/src/app/(dashboard)/review-queue/page.tsx]
- [x] [Review][Patch] **P15: pending_action_list evaluates queryset twice** — FIXED: `len(serializer.data)` instead of `.count()` [backend/core/views/actions.py]
- [x] [Review][Patch] **P16: Toolbar label says "subscribers" but counts actions** — FIXED: changed to "actions" [frontend/src/components/review/BatchActionToolbar.tsx]
- [x] [Review][Patch] **P17: PendingAction updated_at not refreshed on status changes** — FIXED: added `updated_at` to `update_fields` and bulk `.update()` [backend/core/views/actions.py]
- [x] [Review][Patch] **P18: Double audit event in supervised _queue_immediate_retry** — FIXED: removed duplicate; `_process_supervised_queue` handles it [backend/core/tasks/polling.py]
- [x] [Review][Patch] **P19: action_ids not validated for type/shape** — FIXED: type check before processing [backend/core/views/actions.py]

#### Deferred (pre-existing / out of scope)
- [x] [Review][Defer] **W1: _check_subscription_cancellations not using _safe_transition** — Pre-existing code calls `subscriber.mark_passive_churn()` directly; TransitionNotAllowed would crash polling task. [backend/core/tasks/polling.py] — deferred, pre-existing
- [x] [Review][Defer] **W2: Business logic (decision loop) lives in batch approve view** — Architecture says "no business logic in views" but orchestration is inline. Functional, refactor later. [backend/core/views/actions.py] — deferred, architectural
- [x] [Review][Defer] **W3: _safe_transition TOCTOU race needs select_for_update** — `method()` then `save()` without row locking; concurrent save can overwrite state. Needs broader DB-level fix. [backend/core/services/recovery.py] — deferred, systemic
- [x] [Review][Defer] **W4: formatCents hardcodes USD currency** — Multi-currency not in scope for this story. [frontend/src/components/review/PendingActionRow.tsx] — deferred, future feature
- [x] [Review][Defer] **W5: process_retry_result stale in-memory status check** — `_safe_transition` handles the TransitionNotAllowed case; deeper fix needs refresh_from_db pattern. [backend/core/services/recovery.py] — deferred, systemic

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- All 22 backend tests pass (281 total, 8 pre-existing billing webhook failures unrelated)
- All 14 frontend tests pass (73 total, 8 pre-existing failures unrelated)

### Completion Notes List
- Task 1: Added `excluded_from_automation` BooleanField to Subscriber model
- Task 2: Created PendingAction model with TenantScopedModel inheritance, status FSM (pending/approved/excluded)
- Task 3: Wired supervised mode into polling — creates PendingAction instead of executing. Fraud exception executes immediately. Card update detection routes through supervised queue for supervised accounts. Excluded subscribers skipped.
- Task 4: Created GET /api/v1/actions/pending/ endpoint with PendingActionSerializer returning human-readable labels
- Task 5: Created POST /api/v1/actions/batch/ with per-action error tracking, partial failure support (200 with counts)
- Task 6: Created POST /api/v1/subscribers/{id}/exclude/ — sets flag, marks pending actions excluded, clears retries, writes audit
- Task 7: Added pending_action_count to dashboard summary response
- Task 8: Wired all 3 new URL routes in core/urls.py
- Task 9: Created review queue page at /review-queue with table layout, pre-selected rows, zero-state
- Task 10: Created BatchActionToolbar — sticky bottom toolbar with role="toolbar", approve/exclude/deselect actions
- Task 11: Created useBatchAction mutation hook with query invalidation
- Task 12: Created ExclusionDialog confirmation with useExcludeSubscriber mutation
- Task 13: Added badge count on Review Queue nav item using pending_action_count from dashboard summary
- Task 14: Backend tests — 22 tests covering supervised polling, batch approval, exclusion, tenant isolation, pending count
- Task 15: Frontend tests — 14 tests covering review queue rendering, pre-selection, toolbar, batch, exclusion dialog, zero-state

### Change Log
- 2026-04-14: Implemented Story 3.4 — Supervised mode pending action queue and batch approval

### File List

**New files:**
- backend/core/models/pending_action.py
- backend/core/migrations/0011_subscriber_excluded_and_pending_action.py
- backend/core/views/actions.py
- backend/core/serializers/actions.py
- backend/core/tests/test_tasks/test_polling_supervised.py
- backend/core/tests/test_api/test_batch.py
- frontend/src/types/actions.ts
- frontend/src/hooks/usePendingActions.ts
- frontend/src/hooks/useBatchAction.ts
- frontend/src/hooks/useExcludeSubscriber.ts
- frontend/src/app/(dashboard)/review-queue/page.tsx
- frontend/src/components/review/BatchActionToolbar.tsx
- frontend/src/components/review/PendingActionRow.tsx
- frontend/src/components/review/ExclusionDialog.tsx
- frontend/src/__tests__/ReviewQueuePage.test.tsx
- frontend/src/__tests__/BatchActionToolbar.test.tsx

**Modified files:**
- backend/core/models/subscriber.py — added excluded_from_automation field
- backend/core/models/__init__.py — registered PendingAction
- backend/core/tasks/polling.py — added supervised mode branching and _process_supervised_queue()
- backend/core/urls.py — added actions/pending, actions/batch, subscribers/exclude routes
- backend/core/views/dashboard.py — added pending_action_count to summary
- backend/core/serializers/dashboard.py — added pending_action_count field
- frontend/src/types/dashboard.ts — added pending_action_count to DashboardSummary
- frontend/src/components/common/NavBar.tsx — added badge count on Review Queue tab
