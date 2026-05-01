# Story 3.4 (v1): Bulk Send & Status Polling

Status: done

> **v1 scope (post-2026-04-29 simplification).** Replaces the quarantined `3-4-supervised-mode-pending-action-queue-batch-approval.md` (v0). v1 has no Supervised mode, no PendingAction queue, no automated retries — Marc bulk-selects rows on the failed-payments dashboard, confirms in a dialog, and SafeNet dispatches the chosen dunning emails. Daily polling (not engine-driven) drives the only automatic status transitions left in v1. See `_bmad-output/sprint-change-proposal-2026-04-29.md`.

> **Inheriting infrastructure already on `main`** (do NOT recreate):
> - `Subscriber` FSM with `recover()` (active → recovered), `mark_passive_churn()`, `mark_fraud_flagged()`, `mark_resolved_manually()` — `backend/core/models/subscriber.py:32-60`. The `post_transition` signal at `subscriber.py:102-114` writes a `status_<target>` audit on every transition.
> - `_passes_gates(...)` 6-gate sequence with `bypass_engine_active` kwarg — `backend/core/tasks/notifications.py:31-102`. Story 3.3 v1 added the bypass for `send_dunning_email`; **Story 3.4 v1 extends the same bypass to `send_recovery_confirmation`** (Task 3.2).
> - Celery task `send_dunning_email(failure_id, email_type)` for client-manual sends — `backend/core/tasks/notifications.py:387-484`. **Story 3.4 v1's `/batch-send-email/` view enqueues this same task once per accepted selection** (Task 1.6).
> - Celery task `send_recovery_confirmation(failure_id)` — `backend/core/tasks/notifications.py:289-381`. v0 caller is `process_retry_result` (quarantined retry-success path); v1 caller is the new `_check_payment_recoveries` polling helper (Task 3).
> - `send_email` view (`backend/core/views/send_email.py:53-183`) — the per-row contract Story 3.4 mirrors for batch (DPA → tier → validation → tenant → opt-out → exclusion → enqueue ordering).
> - `_SendEmailThrottle` / `_MarkResolvedThrottle` `SimpleRateThrottle` subclasses with explicit `get_cache_key(request, view)` — `backend/core/views/send_email.py:24-50`. Story 3.4 adds a sibling `_BatchSendEmailThrottle` (Task 1.2).
> - `require_dpa_accepted(account)` returning either a 403 Response or None — `backend/core/services/dpa.py:25-43`.
> - `write_audit_event(...)` helper — `backend/core/services/audit.py:11-50`.
> - `Subscriber.objects.for_account(account.id)` / `SubscriberFailure.objects.for_account(account.id)` tenant-scope manager — `backend/core/models/base.py:13-15`.
> - `NotificationOptOut` per-`(subscriber_email, account)` model with case-insensitive opt-out check — `backend/core/models/notification.py:57-69`.
> - `NotificationLog` partial unique constraint on `(failure, email_type) WHERE status="sent"` — `backend/core/models/notification.py:42-54`. Source of truth for "send at most once per (failure, email_type)".
> - Daily Celery beat schedule `daily-failure-poll` running `poll_new_failures` every 86_400s → fan-out to `poll_account_failures.delay(account_id)` per StripeConnection — `backend/safenet_backend/celery.py:13-22`, `backend/core/tasks/polling.py:29-42`.
> - `poll_account_failures(account_id)` orchestration (free-tier frequency gate, missed-cycle alert, PaymentIntent.list ingestion) — `backend/core/tasks/polling.py:45-175`.
> - `_check_subscription_cancellations(account, access_token)` already transitions Active → Passive Churn for `{canceled, unpaid, paused, cancel_at_period_end}` — `backend/core/tasks/polling.py:357-410`. **Story 3.4 v1 ungates this from `is_engine_active`** (Task 2.2).
> - `MAX_BATCH_SIZE = 100` precedent in `backend/core/views/actions.py:13` — Story 3.4 v1 reuses the same cap for batch send.
> - `Subscriber.email` is `EmailField(blank=True, default="")` — empty for cus_* records that have no charge metadata yet; the per-row `send_email` view's "subscriber must be ACTIVE + email present" gates apply to each batch element too (Task 1.5).
> - DRF `ScopedRateThrottle` registered as default; `DEFAULT_THROTTLE_RATES` in `backend/safenet_backend/settings/base.py:104-110` — Story 3.4 adds one new scope `batch_send_email`.
> - Per-scope throttled-message map in `backend/core/views/errors.py:6-22`. Story 3.4 adds a `batch_send_email` entry (Task 1.4).
> - Frontend `<Toaster />` mounted in `frontend/src/app/providers.tsx` (Story 3.3 v1 mounted it; Story 3.4 reuses).
> - Frontend `FailedPaymentsList` (`frontend/src/components/dashboard/FailedPaymentsList.tsx:350-441`) — Story 3.4 inserts a leading checkbox column + bulk toolbar without changing the existing `ActionButtons` column.
> - Frontend `Checkbox` primitive (Base UI) at `frontend/src/components/ui/checkbox.tsx`. Use this — do NOT introduce a parallel checkbox component.
> - Frontend `Dialog` / `DialogContent` / `DialogHeader` / `DialogTitle` / `DialogDescription` / `DialogFooter` shadcn primitives at `frontend/src/components/ui/dialog.tsx`. Use these for the confirmation dialog (Task 8).
> - Frontend `useFailedPayments` query hook with key `["failed-payments", sort, dir]` — `frontend/src/hooks/useFailedPayments.ts:12-28`.
> - Frontend `useSendEmail` mutation hook returning `SendEmailError` (with `code` + `retryAfterSeconds`) — `frontend/src/hooks/useSendEmail.ts`. Story 3.4's bulk hook reuses the **same error envelope shape** so toast handling is identical.
> - Frontend `useMarkResolved` and `useExcludeSubscriber` per-row mutations — `frontend/src/hooks/useMarkResolved.ts`, `useExcludeSubscriber.ts`. Bulk Mark resolved (N) + Exclude (N) fan out client-side over these endpoints (Task 9).
> - Frontend types `FailedPayment`, `RecommendedEmailType`, `SendableEmailType` — `frontend/src/types/failed_payment.ts:1-25`, `frontend/src/hooks/useSendEmail.ts:8`. Reuse — do NOT duplicate.

## Story

As a Mid-tier founder,
I want to bulk-send dunning emails for multiple selected failed-payment rows, and trust SafeNet to detect when subscribers pay or cancel through daily polling,
So that I can cover the high-leverage moves quickly without micromanaging each subscriber, and the dashboard stays accurate without me reconciling every status by hand.

## Acceptance Criteria

1. **Given** the failed-payments list rendered for a Mid/Pro account with DPA accepted **When** the client clicks the per-row checkbox in the new leading column **Then** the row visually marks selected (Base UI `Checkbox` data-checked styling) **And** the `BulkActionToolbar` slides up from the bottom of the viewport with `role="toolbar"`, an `aria-live="polite"` selection-count, and four buttons in this exact order: primary "Send recommended (N)" (variant=default), secondary "Send specific…" (variant=outline, opens email-type picker), tertiary "Mark resolved (N)" (variant=ghost), tertiary "Exclude (N)" (variant=ghost), plus a "Deselect all" link (FR54, UX-DR8 reframed). The toolbar is hidden when N==0. A "Select all (M)" checkbox sits in the table header; toggling it selects/deselects only the currently-rendered rows (sort-aware).

2. **Given** N rows selected and at least one has `recommended_email_type !== null` **When** the client clicks "Send recommended (N)" **Then** a confirmation dialog opens (Base UI Dialog — focus trapped, ESC closes) showing: a header "Send N dunning emails?", a per-row summary list (subscriber email + recommended-email label), a per-type rollup line (e.g., "Update Payment ×3 · Final Notice ×1"), a "Cancel" button, and a "Send all" primary button. Rows whose `recommended_email_type === null` are listed under a separate "Skipped (no recommendation): K" section and are NOT included in the dispatch payload — they are silently filtered before the POST.

3. **Given** the client confirms the recommended bulk send **When** `POST /api/v1/subscribers/batch-send-email/` is called with body `{"selections": [{"subscriber_id": <int>, "failure_id": <int>, "email_type": <"update_payment"|"retry_reminder"|"final_notice">}, ...]}` **Then** the view runs gates in this order: DPA → tier → batch-shape validation (selections non-empty list, ≤100 entries, each entry has all 3 keys with correct types and a CLIENT_MANUAL_EMAIL_TYPES email_type) → for each selection in input order: tenant scoping (subscriber + failure) → subscriber.status==STATUS_ACTIVE → opt-out check → exclusion check → enqueue `send_dunning_email.delay(failure_id, email_type)` + write audit `email_sent` (actor=client, metadata.trigger=`"client_manual"`, metadata.batch=true, metadata.email_type, metadata.failure_id) **And** per-selection failures (subscriber_not_found, failure_not_found, invalid_state, opt_out, excluded) are collected into `failures: [{subscriber_id, failure_id, code, message}]` without aborting the batch — each gate-rejection writes `email_sent_blocked` (actor=client, metadata.reason matches the rejection cause). The response is `200 OK` with body `{"data": {"queued": <int>, "failed": <int>, "failures": [...], "selections_total": <int>}}`. One summary audit row per request: actor=client, action=`batch_email_send`, outcome=`success` (failed==0 ∧ queued>0) | `partial` (queued>0 ∧ failed>0) | `failed` (queued==0 ∧ failed>0), metadata={selections_total, queued, failed, trigger:"client_manual"}.

4. **Given** the bulk-send request body fails shape validation (selections missing/not-list, >100 entries, malformed entry) **When** the view validates **Then** the response is `400 VALIDATION_ERROR` with envelope `{"error": {"code": "VALIDATION_ERROR", "message": <specific>, "field": <"selections" | "selections[<i>].<key>">}}` **And** no Celery tasks are enqueued **And** no audit rows are written. Booleans are rejected as integers (`isinstance(v, int) and not isinstance(v, bool)`) for `subscriber_id` and `failure_id`, mirroring Story 3.3 v1's review patch.

5. **Given** an account that has already POSTed 5 successful batch-send requests within the last 60 seconds **When** the client confirms a 6th batch within the window **Then** the API responds `429 RATE_LIMITED` with envelope `{"error": {"code": "RATE_LIMITED", "message": "Too many batch send requests. Try again later.", "field": null}}` and the standard DRF `Retry-After` header **And** the frontend bulk hook surfaces a `toast.error("Rate limit reached. Try again in <N>s.", { duration: 6000 })` **And** the toolbar's primary button becomes interactive again as soon as the cooldown elapses (no permanent disable). The 5/min batch-send scope is independent of the per-row 10/min `send_email` scope — a user who exhausted per-row sends can still issue a batch.

6. **Given** the client clicks "Send specific…" with N rows selected **When** the email-type picker opens **Then** it lists the same three options as the per-row dropdown (Update payment / Retry reminder / Final notice) in that exact order **And** picking one opens the same confirmation dialog as AC #2 with EVERY selected row's email_type set to the chosen type (no per-row recommendation override) **And** confirming dispatches a single `/batch-send-email/` request with selections all carrying that email_type. Rows with `subscriber_status !== "active"` are excluded client-side from the selections payload (they would 422 server-side anyway — reject early to keep the user feedback clean).

7. **Given** the daily polling Celery task `poll_account_failures` runs **When** the helper `_check_subscription_cancellations(account, access_token)` discovers an Active subscriber whose Stripe subscription state is `canceled`, `unpaid`, `paused`, or whose `cancel_at_period_end` is true **Then** the subscriber transitions Active → Passive Churn via `mark_passive_churn()` **And** the existing `subscription_cancellation_detected` audit row is written with `metadata.reason` equal to the specific Stripe state ("canceled" / "unpaid" / "paused" / "cancel_at_period_end") (FR18) **And** the post_transition signal writes the `status_passive_churn` audit row. Story 3.4 v1's change is to lift this helper out of the `is_engine_active(account)` gate inside `poll_account_failures` so it runs for every account where polling fires (Free-tier still gates via the existing free-tier polling-frequency check at the top of `poll_account_failures`; v1 Mid/Pro accounts no longer need `engine_mode` set).

8. **Given** the daily polling Celery task runs **When** the new helper `_check_payment_recoveries(account, access_token)` finds an Active subscriber with at least one `SubscriberFailure` whose `payment_intent_id`, when re-fetched via `stripe.PaymentIntent.retrieve`, returns `status == "succeeded"` **Then** the subscriber transitions Active → Recovered via `subscriber.recover()` **And** any `next_retry_at` on that subscriber's failures is cleared (defense-in-depth — v1 doesn't schedule retries, but quarantined v0 code on main may have left stale rows) **And** an audit row is written: actor=`engine`, action=`payment_success_detected`, outcome=`success`, metadata={payment_intent_id, failure_id, polling_cycle_at} **And** for Mid/Pro accounts with DPA accepted, `send_recovery_confirmation.delay(failure.id, bypass_engine_active=True)` is dispatched (FR17, FR25 → Story 4.3 owns email content). Free-tier and unsigned-DPA accounts skip the recovery email dispatch (the FSM transition still happens so the dashboard reflects truth).

9. **Given** `send_recovery_confirmation` is invoked with `bypass_engine_active=True` **When** the task runs **Then** it skips Gate 1 (engine_active) but enforces Gates 2–6 unchanged (no_email, excluded, opt_out, duplicate, final_notice→active is irrelevant here since email_type is `recovery_confirmation`) **And** the existing v0 caller (`process_retry_result` in `recovery.py:281-289`) — which still lives on main inside the quarantined retry path — continues to dispatch with default `bypass_engine_active=False`, preserving behavior for any reactivated v0 environment **And** the success-path `notification_sent` audit metadata gains `trigger="polling_recovery"` when the bypass is true, mirroring Story 3.3's `trigger="client_manual"` convention.

10. **Given** a Free-tier account **When** the failed-payments list renders **Then** the leading checkbox column is present but every per-row checkbox is `disabled` with the existing tier tooltip `"Upgrade to Mid or Pro to enable email actions"` **And** the header "select all" checkbox is also disabled **And** the toolbar never appears (selection state is forced empty for Free-tier — checkbox change handlers are no-ops when `tier === "free"`) **And** the existing inline upgrade banner above the table (Story 3.2 v1) remains the visible CTA. Pre-existing per-row buttons stay disabled with their tier tooltip from Story 3.3 v1.

11. **Given** the bulk Mark resolved (N) action is clicked with N selected rows **When** the client confirms a "Mark N as resolved?" dialog **Then** the frontend fans out N parallel calls to the existing `POST /api/v1/subscribers/{id}/mark-resolved/` endpoint via `Promise.allSettled` **And** the `mark_resolved` throttle scope is increased from `10/min` to `60/min` to support batches up to ~50 rows (settings change — see Task 11.1) **And** per-call failures are aggregated into a single result toast: success `Marked N as resolved.` (when all settled fulfilled), partial `Marked X / N as resolved — Y failed.` (with `toast.warning`, duration 8000), full failure `Failed to mark N as resolved.` (with `toast.error`, duration 6000). Bulk Exclude (N) follows the identical fan-out pattern over `/exclude/{id}/` (which has no throttle). The failed-payments cache is invalidated ONCE after the fan-out settles (single `invalidateQueries({queryKey: ["failed-payments"]})` call), not per-mutation, to avoid N rerenders during the in-flight period.

## Tasks / Subtasks

### Backend

- [x] **Task 1: New view `batch_send_email`** (AC: #3, #4, #5, #6)
  - [x] 1.1 Create `backend/core/views/batch_send_email.py` (do not bloat `send_email.py` — keep one route per file per `architecture.md#Structure Patterns:439-477`). Imports:
    ```python
    from rest_framework import status
    from rest_framework.decorators import api_view, permission_classes, throttle_classes
    from rest_framework.permissions import IsAuthenticated
    from rest_framework.response import Response
    from rest_framework.throttling import SimpleRateThrottle

    from core.engine.state_machine import STATUS_ACTIVE
    from core.models.account import TIER_FREE
    from core.models.notification import NotificationOptOut
    from core.models.subscriber import Subscriber, SubscriberFailure
    from core.services.audit import write_audit_event
    from core.services.dpa import require_dpa_accepted
    from core.tasks.notifications import CLIENT_MANUAL_EMAIL_TYPES, send_dunning_email
    ```
  - [x] 1.2 Define `_BatchSendEmailThrottle` mirroring `_SendEmailThrottle` exactly (subclass `SimpleRateThrottle`, `scope="batch_send_email"`, override `get_cache_key` to key on `request.user.pk`). Do NOT use `ScopedRateThrottle` — Story 3.3 v1's debug log captured why (DRF overwrites `self.scope` from `view.throttle_scope`, which is `None` for `@api_view` function views — the throttle silently no-ops).
  - [x] 1.3 Define module-level `MAX_BATCH_SIZE = 100` (parity with `actions.py:13`).
  - [x] 1.4 Edit `backend/safenet_backend/settings/base.py:104-110`. Add `"batch_send_email": "5/min"` to `DEFAULT_THROTTLE_RATES`. Edit `backend/core/views/errors.py:6-10`. Add `"batch_send_email": "Too many batch send requests. Try again later."` to `_THROTTLED_MESSAGES`.
  - [x] 1.5 Implement the view body. Critical ordering: **DPA → tier → batch-shape → per-selection (tenant lookup → status → opt-out → exclusion → enqueue + audit)**. Per-row processing is intentionally NOT wrapped in `transaction.atomic()` — partial-failure semantics demand that successful enqueues persist their audit rows even if a later selection's lookup raises. Each per-selection helper writes its own audit row.
    ```python
    @api_view(["POST"])
    @permission_classes([IsAuthenticated])
    @throttle_classes([_BatchSendEmailThrottle])
    def batch_send_email(request):
        """POST /api/v1/subscribers/batch-send-email/ — fan-out per-selection enqueue."""
        try:
            account = request.user.account
        except request.user.__class__.account.RelatedObjectDoesNotExist:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "No account found.", "field": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Gate 1: DPA — must be FIRST so unsigned accounts get DPA_REQUIRED, not VALIDATION_ERROR.
        dpa_response = require_dpa_accepted(account)
        if dpa_response is not None:
            return dpa_response

        # Gate 2: tier
        if account.tier == TIER_FREE:
            return Response(
                {"error": {"code": "TIER_REQUIRED",
                           "message": "Upgrade to Mid or Pro to enable email actions.",
                           "field": None}},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Gate 3: body shape
        selections = request.data.get("selections")
        if not isinstance(selections, list) or not selections:
            return _validation("selections must be a non-empty list.", "selections")
        if len(selections) > MAX_BATCH_SIZE:
            return _validation(f"Maximum {MAX_BATCH_SIZE} selections per batch.", "selections")

        # Gate 4: per-entry shape — strict types, no booleans-as-int
        for i, sel in enumerate(selections):
            if not isinstance(sel, dict):
                return _validation(f"selections[{i}] must be an object.", f"selections[{i}]")
            sid, fid, etype = sel.get("subscriber_id"), sel.get("failure_id"), sel.get("email_type")
            if not isinstance(sid, int) or isinstance(sid, bool):
                return _validation("subscriber_id must be an integer.", f"selections[{i}].subscriber_id")
            if not isinstance(fid, int) or isinstance(fid, bool):
                return _validation("failure_id must be an integer.", f"selections[{i}].failure_id")
            if etype not in CLIENT_MANUAL_EMAIL_TYPES:
                return _validation(
                    f"email_type must be one of {list(CLIENT_MANUAL_EMAIL_TYPES)}.",
                    f"selections[{i}].email_type",
                )

        # Per-selection processing — collect failures, enqueue successes
        queued, failed, failures = 0, 0, []
        for sel in selections:
            outcome = _process_one_selection(
                account, sel["subscriber_id"], sel["failure_id"], sel["email_type"],
            )
            if outcome["ok"]:
                queued += 1
            else:
                failed += 1
                failures.append({
                    "subscriber_id": sel["subscriber_id"],
                    "failure_id": sel["failure_id"],
                    "code": outcome["code"],
                    "message": outcome["message"],
                })

        summary = "success" if failed == 0 else ("partial" if queued > 0 else "failed")
        write_audit_event(
            subscriber=None,
            actor="client",
            action="batch_email_send",
            outcome=summary,
            metadata={
                "selections_total": len(selections),
                "queued": queued,
                "failed": failed,
                "trigger": "client_manual",
            },
            account=account,
        )
        return Response(
            {"data": {
                "queued": queued, "failed": failed, "failures": failures,
                "selections_total": len(selections),
            }},
            status=status.HTTP_200_OK,
        )


    def _validation(message: str, field: str) -> Response:
        return Response(
            {"error": {"code": "VALIDATION_ERROR", "message": message, "field": field}},
            status=status.HTTP_400_BAD_REQUEST,
        )


    def _process_one_selection(account, sid: int, fid: int, etype: str) -> dict:
        """Per-row gate sequence + enqueue. Returns {'ok': bool, 'code'?, 'message'?}."""
        try:
            subscriber = Subscriber.objects.for_account(account.id).get(id=sid)
        except Subscriber.DoesNotExist:
            return {"ok": False, "code": "NOT_FOUND", "message": "Subscriber not found."}

        try:
            failure = SubscriberFailure.objects.for_account(account.id).get(
                id=fid, subscriber_id=subscriber.id,
            )
        except SubscriberFailure.DoesNotExist:
            return {"ok": False, "code": "NOT_FOUND",
                    "message": "Failure not found for this subscriber."}

        if subscriber.status != STATUS_ACTIVE:
            _audit_blocked(account, subscriber, fid, etype,
                           reason="invalid_state",
                           extra={"subscriber_status": subscriber.status})
            return {"ok": False, "code": "INVALID_STATE",
                    "message": f"Cannot send email — subscriber status is '{subscriber.status}'."}

        sub_email = (subscriber.email or "").strip().lower()
        if sub_email and NotificationOptOut.objects.for_account(account.id).filter(
            subscriber_email__iexact=sub_email,
        ).exists():
            _audit_blocked(account, subscriber, fid, etype, reason="opt_out")
            return {"ok": False, "code": "OPT_OUT",
                    "message": "Subscriber has opted out of notifications."}

        if subscriber.excluded_from_automation:
            _audit_blocked(account, subscriber, fid, etype, reason="excluded")
            return {"ok": False, "code": "EXCLUDED",
                    "message": "Subscriber is excluded from automation."}

        send_dunning_email.delay(fid, etype)
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="client",
            action="email_sent",
            outcome="success",
            metadata={"email_type": etype, "trigger": "client_manual",
                      "failure_id": fid, "batch": True},
            account=account,
        )
        return {"ok": True}


    def _audit_blocked(account, subscriber, failure_id, email_type, *, reason, extra=None):
        meta = {"reason": reason, "email_type": email_type,
                "failure_id": failure_id, "batch": True}
        if extra:
            meta.update(extra)
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="client",
            action="email_sent_blocked",
            outcome="skipped",
            metadata=meta,
            account=account,
        )
    ```
  - [x] 1.6 Each accepted selection enqueues `send_dunning_email.delay(failure_id, email_type)` — the same task Story 3.3 v1 routes per-row sends through. The dedup constraint on `NotificationLog` is the floor; resubmitting the same batch logs `duplicate_race` for already-sent (failure, email_type) pairs without re-billing Resend.
  - [x] 1.7 Rate-limit semantics: `_BatchSendEmailThrottle` (5/min) is independent of `_SendEmailThrottle` (10/min). The two scopes are separate cache keys (`throttle_batch_send_email_<user.pk>` vs `throttle_send_email_<user.pk>`), so a per-row exhaustion does not affect batch dispatches and vice versa.

- [x] **Task 2: Wire the new URL + ungate cancellation polling** (AC: #3, #7)
  - [x] 2.1 Edit `backend/core/urls.py:6,12-32`. Add `from core.views.batch_send_email import batch_send_email`. Add the route directly under the existing `/send-email/` line — placement matters because Django URL resolution is first-match: place `batch-send-email/` (literal) BEFORE the `<int:subscriber_id>/...` routes so the `int` converter does not try to parse the literal string:
    ```python
    path("v1/subscribers/batch-send-email/", batch_send_email, name="batch_send_email"),
    path("v1/subscribers/<int:subscriber_id>/exclude/", exclude_subscriber, name="exclude_subscriber"),
    path("v1/subscribers/<int:subscriber_id>/send-email/", send_email, name="subscriber_send_email"),
    path("v1/subscribers/<int:subscriber_id>/mark-resolved/", mark_resolved, name="subscriber_mark_resolved"),
    ```
  - [x] 2.2 Edit `backend/core/tasks/polling.py:156-158`. Current code:
    ```python
    # Check for subscription cancellations (AC7)
    if is_engine_active(account):
        _check_subscription_cancellations(account, access_token)
    ```
    Replace with:
    ```python
    # Story 3.4 v1: ungate from is_engine_active so v1 accounts (engine_mode=None)
    # get cancellation-driven Active → Passive Churn transitions every cycle.
    # Free-tier accounts still gate at the top of poll_account_failures via
    # get_polling_frequency(account).
    _check_subscription_cancellations(account, access_token)

    # Story 3.4 v1: new payment-recovery detection (Active → Recovered).
    _check_payment_recoveries(account, access_token)
    ```
    Leave the `_detect_card_updates` block (line 152-154) unchanged — it stays gated behind `is_engine_active`, which is False for v1, so it remains effectively quarantined per `sprint-change-proposal-2026-04-29.md §2d` ("card-update detection removed entirely from v1").
  - [x] 2.3 The existing `_check_subscription_cancellations` body (`polling.py:357-410`) needs no edits: it already (a) iterates Active subscribers, (b) calls `subscriber.mark_passive_churn()`, (c) writes `subscription_cancellation_detected` audit, (d) clears stale `next_retry_at`. AC #7 is satisfied by the call-site ungating alone.

- [x] **Task 3: Add `_check_payment_recoveries` polling helper + extend `send_recovery_confirmation`** (AC: #8, #9)
  - [x] 3.1 Add to `backend/core/tasks/polling.py` directly after `_check_subscription_cancellations`. File flow becomes: cancellation detection → recovery detection → card-update detection (still quarantined) → fingerprint helper.
    ```python
    # Cap the lookback window to bound Stripe API calls. v1 dashboard only shows
    # current-month failures (Story 3.2 v1), so 90 days covers any subscriber
    # whose failure could still be Active.
    RECOVERY_LOOKBACK_DAYS = 90


    def _check_payment_recoveries(account, access_token):
        """Story 3.4 v1 — detect previously-failed PaymentIntents that have since succeeded.

        For each Active subscriber, refetch every recent failure's PaymentIntent. If Stripe
        now reports `status == "succeeded"`, transition Active → Recovered and (for Mid/Pro
        accounts with DPA accepted) dispatch the recovery confirmation email per FR25 +
        Story 4.3.
        """
        from core.engine.state_machine import STATUS_ACTIVE
        from core.models.account import TIER_MID, TIER_PRO
        from core.models.subscriber import Subscriber, SubscriberFailure

        cutoff = timezone.now() - timedelta(days=RECOVERY_LOOKBACK_DAYS)
        send_email_eligible = (
            account.tier in (TIER_MID, TIER_PRO) and account.dpa_accepted
        )

        active_subscribers = (
            Subscriber.objects.for_account(account.id)
            .filter(status=STATUS_ACTIVE)
            .order_by("id")
        )

        for subscriber in active_subscribers:
            # Order ASC by failure_created_at so the OLDEST recovered PI drives
            # the transition + (one) recovery confirmation email per subscriber.
            failures = (
                SubscriberFailure.objects.for_account(account.id)
                .filter(subscriber=subscriber, failure_created_at__gte=cutoff)
                .order_by("failure_created_at")
            )

            for failure in failures:
                try:
                    pi = stripe.PaymentIntent.retrieve(
                        failure.payment_intent_id, api_key=access_token,
                    )
                except stripe.StripeError as exc:
                    logger.warning(
                        "Failed to retrieve PaymentIntent %s for recovery check: %s",
                        failure.payment_intent_id, exc,
                    )
                    continue

                if pi.status != "succeeded":
                    continue

                # Atomic: lock + transition + audit + clear stale retry rows.
                with transaction.atomic():
                    locked = (
                        Subscriber.objects.for_account(account.id)
                        .select_for_update()
                        .get(id=subscriber.id)
                    )
                    if locked.status != STATUS_ACTIVE:
                        # Concurrent transition (e.g., manual resolve) — bail.
                        break

                    locked.recover()
                    locked.save(update_fields=["status"])

                    SubscriberFailure.objects.for_account(account.id).filter(
                        subscriber=locked, next_retry_at__isnull=False,
                    ).update(next_retry_at=None)

                    write_audit_event(
                        subscriber=str(locked.id),
                        actor="engine",
                        action="payment_success_detected",
                        outcome="success",
                        metadata={
                            "payment_intent_id": failure.payment_intent_id,
                            "failure_id": str(failure.id),
                            "polling_cycle_at": timezone.now().isoformat(),
                        },
                        account=account,
                    )

                if send_email_eligible:
                    from core.tasks.notifications import send_recovery_confirmation
                    failure_id = failure.id
                    transaction.on_commit(
                        lambda fid=failure_id: send_recovery_confirmation.delay(
                            fid, bypass_engine_active=True,
                        )
                    )

                # First successful PI per subscriber drives one transition; bail.
                break
    ```
    Notes for the implementer:
    - The `select_for_update` lock prevents racing with `mark_resolved_manually` from Story 3.3 (which uses the same pattern — its review patch hardened the FSM transition path).
    - The `break` after the first matched failure is intentional: a subscriber transitions Active → Recovered exactly once. If they have 3 failures and 1 has paid, transitioning after the first is correct.
    - `transaction.on_commit` defers Celery dispatch until after the FSM transition commits; a rollback never leaves a phantom recovery email enqueued.
    - The lambda's `fid=failure_id` default-argument capture avoids the standard for-loop-closure pitfall (no `for` loop here, but the pattern is ingrained — preserve it for consistency with `recovery.py:281-289`).
    - **N+1 Stripe call concern is acknowledged and deferred** — Stripe has no batch retrieve API, and v1's failed-payments universe is bounded (current-month per Story 3.2 v1; 90-day lookback as the active-subscriber bound here). Optimization belongs to v2.

  - [x] 3.2 Edit `backend/core/tasks/notifications.py:289-381` (`send_recovery_confirmation` task). Add a `bypass_engine_active: bool = False` keyword argument and pass through to `_passes_gates`. Mirror the Story 3.3 v1 change to `send_dunning_email`:
    ```python
    @app.task(bind=True, max_retries=3, default_retry_delay=60)
    def send_recovery_confirmation(self, failure_id: int, bypass_engine_active: bool = False):
        """Send a recovery confirmation email — short acknowledgement after a successful retry (FR25)
        or polling-detected payment recovery (Story 3.4 v1).
        """
        # ... existing setup unchanged ...
        if not _passes_gates(
            subscriber, failure, account,
            email_type=email_type, log_label="send_recovery_confirmation",
            bypass_engine_active=bypass_engine_active,
        ):
            return
        # ... existing send logic unchanged ...
    ```
    On the success-path `write_audit_event`, conditionally include `trigger`:
    ```python
    write_audit_event(
        subscriber=str(subscriber.id),
        actor="engine",
        action="notification_sent",
        outcome="success",
        metadata={
            "email_type": email_type,
            "decline_code": failure.decline_code,
            "resend_message_id": msg_id,
            **({"trigger": "polling_recovery"} if bypass_engine_active else {}),
        },
        account=account,
    )
    ```
    The existing v0 caller `process_retry_result` in `services/recovery.py:281-289` calls `send_recovery_confirmation.delay(failure_id)` (positional only) — backwards-compatible: default `bypass_engine_active=False` preserves the v0 path. Do NOT touch `recovery.py`.

- [x] **Task 4: Backend tests — `batch_send_email` endpoint** (AC: #3, #4, #5, #6)
  - [x] 4.1 Create `backend/core/tests/test_api/test_batch_send_email.py`. Reuse the fixture pattern from `backend/core/tests/test_api/test_send_email.py:18-77` — `mid_account_with_dpa`, `subscriber_with_failure`, `second_user`, `second_account`, `second_auth_client`, plus `auth_client`/`account`/`user` from `backend/core/tests/conftest.py:1-38`. Always include the autouse `cache.clear()` fixture so per-test throttle state resets:
    ```python
    URL = "/api/v1/subscribers/batch-send-email/"

    @pytest.fixture(autouse=True)
    def _clear_throttle_cache():
        cache.clear(); yield; cache.clear()
    ```
  - [x] 4.2 Tests to write (each `@pytest.mark.django_db`):
    - `test_requires_authentication` — unauth POST → 401.
    - `test_dpa_required_returns_403` — Mid-tier no DPA → 403 `DPA_REQUIRED`.
    - `test_dpa_first_even_with_malformed_body` — Mid-tier no DPA + body `{"selections": "not a list"}` → 403 `DPA_REQUIRED` (NOT 400 — gate ordering!).
    - `test_free_tier_returns_403` — DPA accepted but tier=free → 403 `TIER_REQUIRED`.
    - `test_missing_selections_returns_400` — body `{}` → 400 `VALIDATION_ERROR`, field `"selections"`.
    - `test_empty_selections_returns_400` — body `{"selections": []}` → 400.
    - `test_oversize_batch_returns_400` — 101 entries → 400, message references MAX_BATCH_SIZE.
    - `test_malformed_entry_returns_400` — `[{"subscriber_id": "abc", "failure_id": 1, "email_type": "update_payment"}]` → 400, field `"selections[0].subscriber_id"`.
    - `test_boolean_subscriber_id_rejected` — `subscriber_id: True` → 400 (the patch from Story 3.3 review).
    - `test_invalid_email_type_returns_400` — `"banana"` → 400, field `"selections[0].email_type"`.
    - `test_happy_path_queues_one_per_selection` — 3 valid selections referencing distinct (subscriber, failure) pairs. Patch `core.tasks.notifications.send_dunning_email.delay`. POST. Assert response 200, body `{data: {queued: 3, failed: 0, failures: [], selections_total: 3}}`. Assert `delay.call_count == 3` with the right args. Assert 3 audit rows with action=`email_sent`, metadata.batch=True. Assert ONE `batch_email_send` summary audit row with outcome=`success`, metadata.queued=3, metadata.failed=0.
    - `test_partial_failure_returns_per_row_errors` — 2 selections: first valid, second references a non-existent failure_id. POST. Assert 200, queued=1, failed=1, failures=[{subscriber_id, failure_id, code:"NOT_FOUND", message:"Failure not found for this subscriber."}]. Summary outcome=`partial`. Assert ONE `email_sent` audit row (the success). Lookup failures (`NOT_FOUND`) intentionally do NOT write `email_sent_blocked` — only gate rejections (invalid_state / opt_out / excluded) do.
    - `test_invalid_state_blocks_with_audit` — subscriber.status=`recovered`. POST. failures[0].code=`INVALID_STATE`. Audit: action=`email_sent_blocked`, metadata.reason=`invalid_state`, metadata.subscriber_status=`recovered`, metadata.batch=True.
    - `test_opt_out_blocks_with_audit` — pre-create `NotificationOptOut(subscriber_email=sub.email, account=...)`. POST. failures[0].code=`OPT_OUT`. Audit metadata.reason=`opt_out`.
    - `test_excluded_blocks_with_audit` — `subscriber.excluded_from_automation = True`. POST. failures[0].code=`EXCLUDED`.
    - `test_summary_outcome_failed_when_no_successes` — 2 selections, both opt-out. summary outcome=`failed`.
    - `test_tenant_isolation` — first user's batch references a subscriber from `second_account`. POST. failures[0].code=`NOT_FOUND` (tenant scoping treats other-tenant rows as non-existent — same pattern as Story 3.3 v1).
    - `test_rate_limit_429_after_5_requests` — POST 5 valid batches. Mock delay. Assert 5 × 200. 6th POST → 429 `RATE_LIMITED`. `Retry-After` header present and parses as a positive int.
    - `test_batch_throttle_independent_of_per_row` — exhaust per-row send_email throttle (10× POST to `/send-email/`) then issue ONE batch POST → 200 (not 429). Confirms scopes are distinct cache keys.
    - `test_request_with_two_email_types_routes_correctly` — selections=[{..., email_type:"update_payment"}, {..., email_type:"final_notice"}]. Assert delay called with each respective email_type.
    - `test_duplicate_selection_in_batch_double_dispatches` — 2 entries pointing at the SAME (failure_id, email_type). Assert `delay.call_count == 2` (the dedup constraint inside `send_dunning_email` collapses the second send to a `duplicate_race` suppression at task time, not at view time). The view does NOT pre-dedupe.
  - [x] 4.3 Run `docker compose exec -T web poetry run pytest core/tests/test_api/test_batch_send_email.py -v` — all green. (Per the project memory rule, backend tests run inside the docker `web` container.)

- [x] **Task 5: Backend tests — polling status detection (Active → Passive Churn ungated; Active → Recovered new)** (AC: #7, #8, #9)
  - [x] 5.1 Edit `backend/core/tests/test_tasks/test_polling.py`. The autouse fixtures (`_fernet_key`, `_clear_cache`, `_mock_notification_dispatch`) handle cache reset and prevent Redis side effects. Add a new class `TestV1StatusDetection`:
    - `test_cancellation_detection_runs_for_v1_account_without_engine_mode` — Mid+DPA, `engine_mode=None`. `stripe.PaymentIntent.list` returns empty. `stripe.Subscription.list` returns one sub with `status="canceled"`. `stripe.PaymentIntent.retrieve` raises (no recoveries). One Active subscriber. Call `poll_account_failures(account.id)`. Assert `subscriber.status == "passive_churn"`. Assert `subscription_cancellation_detected` audit with metadata.reason=`canceled`. Confirms ungating from `is_engine_active`.
    - `test_cancel_at_period_end_drives_passive_churn` — same shape with `status="active"` + `cancel_at_period_end=True`. Audit metadata.reason=`cancel_at_period_end`.
    - `test_recovery_detection_active_to_recovered` — Mid+DPA. One Active subscriber + one SubscriberFailure (`payment_intent_id="pi_test"`). Mock `stripe.PaymentIntent.retrieve` to return a MagicMock with `status="succeeded"`. Patch `send_recovery_confirmation.delay`. Use `pytest-django`'s `django.test.TestCase.captureOnCommitCallbacks(execute=True)` (subclass `TransactionTestCase` if needed, OR call `transaction.commit()` in the test) so the `transaction.on_commit` lambda fires. Call `_check_payment_recoveries(account, "sk_test")`. Assert `subscriber.status == "recovered"`. Assert `payment_success_detected` audit row with metadata.payment_intent_id, metadata.failure_id. Assert `delay.assert_called_once_with(failure.id, bypass_engine_active=True)`.
    - `test_recovery_skips_when_pi_still_failing` — PI returns `"requires_payment_method"`. Subscriber stays Active. No `payment_success_detected` audit. `delay` NOT called.
    - `test_recovery_skips_when_subscriber_already_recovered` — pre-set status=recovered. Helper called. No transition (FSM source restricts to Active anyway), no audit, no email dispatch.
    - `test_recovery_breaks_after_first_succeeded_pi` — subscriber has 2 failures with `failure_created_at` t1 < t2; both PIs return `"succeeded"`. Helper called. ONE `payment_success_detected` audit (oldest). `delay.call_count == 1`.
    - `test_recovery_clears_stale_next_retry_at` — pre-create v0-style failure with `next_retry_at=timezone.now()+timedelta(hours=1)`. Trigger recovery. Assert `failure.next_retry_at is None`.
    - `test_recovery_skips_email_for_free_tier` — Free-tier with DPA accepted. PI succeeded. FSM transition + `payment_success_detected` audit happen. `send_recovery_confirmation.delay` NOT called.
    - `test_recovery_skips_email_when_no_dpa` — Mid-tier, `dpa_accepted=False`. Same: transition runs, email does not dispatch.
    - `test_recovery_lookback_window_bounds_pi_calls` — pre-create a failure with `failure_created_at=now-100days` (past 90-day cutoff). Stripe call counter for that failure stays 0.
    - `test_stripe_error_during_recovery_check_logs_and_continues` — mock `stripe.PaymentIntent.retrieve` to raise `stripe.APIError`. Helper logs warning, no exception bubbles. Subscriber stays Active.
  - [x] 5.2 Edit `backend/core/tests/test_tasks/test_notifications.py`. Add to `TestSendRecoveryConfirmation` (or create the class if absent — verify with `grep -n "class Test" core/tests/test_tasks/test_notifications.py`):
    - `test_bypass_engine_active_skips_gate_1` — Mid+DPA but `engine_mode=None` (so `is_engine_active` is False). Patch `send_recovery_confirmation_email`. Call task synchronously: `send_recovery_confirmation(failure.id, bypass_engine_active=True)`. Assert builder called + NotificationLog `sent` row written + audit `notification_sent` with metadata.trigger=`polling_recovery`.
    - `test_default_call_preserves_v0_gate_behavior` — Same setup but call `send_recovery_confirmation(failure.id)` (positional only). Assert builder NOT called + NotificationLog `suppressed` row with metadata.reason=`engine_not_active`. Confirms the kwarg is opt-in.
    - `test_bypass_does_not_skip_other_gates` — bypass=True but `subscriber.email = ""`. Assert builder NOT called and `_log_suppression` writes `no_email`.

- [x] **Task 6: Backend tests — quarantine guard for `_detect_card_updates`** (AC: #7)
  - [x] 6.1 Add to `TestV1StatusDetection` in `test_polling.py`:
    - `test_card_update_detection_remains_gated_in_v1` — Mid+DPA, `engine_mode=None` (v1). Patch BOTH `_detect_card_updates` AND `_check_subscription_cancellations` AND `_check_payment_recoveries`. Call `poll_account_failures(account.id)`. Assert `_detect_card_updates` NOT called (still behind `is_engine_active`); `_check_subscription_cancellations` AND `_check_payment_recoveries` BOTH called. Confirms the v0/v1 split: cancellation + recovery helpers run for v1, card-update stays quarantined.

### Frontend

- [x] **Task 7: New mutation hook `useBatchSendEmail`** (AC: #3, #5)
  - [x] 7.1 Create `frontend/src/hooks/useBatchSendEmail.ts`. Mirror `useSendEmail.ts` shape — same axios error wrapping, **reuse `SendEmailError`** for consistency:
    ```typescript
    "use client";

    import { useMutation, useQueryClient } from "@tanstack/react-query";
    import { AxiosError } from "axios";
    import api from "@/lib/api";
    import {
      SendEmailError,
      type SendEmailErrorEnvelope,
      type SendableEmailType,
    } from "@/hooks/useSendEmail";

    export interface BatchSelection {
      subscriber_id: number;
      failure_id: number;
      email_type: SendableEmailType;
    }

    export interface BatchSendFailure {
      subscriber_id: number;
      failure_id: number;
      code: string;
      message: string;
    }

    export interface BatchSendResult {
      queued: number;
      failed: number;
      failures: BatchSendFailure[];
      selections_total: number;
    }

    export function useBatchSendEmail() {
      const queryClient = useQueryClient();
      return useMutation<BatchSendResult, SendEmailError, BatchSelection[]>({
        mutationFn: async (selections) => {
          try {
            const { data } = await api.post<{ data: BatchSendResult }>(
              "/subscribers/batch-send-email/",
              { selections },
            );
            return data.data;
          } catch (err) {
            if (err instanceof AxiosError && err.response) {
              const envelope = (err.response.data?.error ?? {
                code: "UNKNOWN",
                message: "Request failed.",
                field: null,
              }) as SendEmailErrorEnvelope;
              const retryAfter = err.response.headers?.["retry-after"] ?? null;
              throw new SendEmailError(envelope, err.response.status, retryAfter);
            }
            throw err;
          }
        },
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ["failed-payments"] });
          queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
        },
      });
    }
    ```
    Returning the FULL response object lets the consumer (the toolbar component) format the partial-failure toast. Reusing `SendEmailError` keeps the rate-limit / DPA / opt-out toast branching consistent across per-row and bulk surfaces.

- [x] **Task 8: New `BulkActionToolbar` component** (AC: #1, #2, #5, #6, #10)
  - [x] 8.1 Create `frontend/src/components/dashboard/BulkActionToolbar.tsx`. Component is presentational + dispatch-only — selection state is owned by the parent `FailedPaymentsList` (Task 10). Imports:
    ```tsx
    import { Button } from "@/components/ui/button";
    import {
      Dialog,
      DialogContent,
      DialogDescription,
      DialogFooter,
      DialogHeader,
      DialogTitle,
    } from "@/components/ui/dialog";
    import {
      DropdownMenu,
      DropdownMenuContent,
      DropdownMenuItem,
      DropdownMenuTrigger,
    } from "@/components/ui/dropdown-menu";
    import { ChevronDownIcon } from "lucide-react";
    import { useState } from "react";
    import type { FailedPayment } from "@/types/failed_payment";
    import type { BatchSelection } from "@/hooks/useBatchSendEmail";
    import type { SendableEmailType } from "@/hooks/useSendEmail";
    ```
  - [x] 8.2 Props:
    ```tsx
    interface BulkActionToolbarProps {
      selectedRows: FailedPayment[];     // full row objects — for confirmation dialog
      isPending: boolean;                // any of the 3 mutations in flight
      pendingLabel?: string;             // "Sending…" / "Marking resolved…" / "Excluding…"
      onSendRecommended: (selections: BatchSelection[], skipped: FailedPayment[]) => void;
      onSendSpecific: (selections: BatchSelection[], emailType: SendableEmailType) => void;
      onMarkResolved: (rows: FailedPayment[]) => void;
      onExclude: (rows: FailedPayment[]) => void;
      onDeselectAll: () => void;
    }
    ```
  - [x] 8.3 Render a fixed-bottom toolbar (`role="toolbar"`, `aria-label="Bulk actions"`, `aria-live="polite"` on the count line). Visual tokens: copy from `frontend/src/components/review/BatchActionToolbar.tsx:23-46` (positioning, color tokens, shadow). Do NOT IMPORT that v0 component — its props are tightly coupled to PendingAction and its UI semantics differ. Build a parallel component in `dashboard/`. The v0 toolbar's path is on the quarantine list (review-queue/page.tsx) so importing would couple v1 to v0.
  - [x] 8.4 Confirmation dialog state lives inside the component (`useState<DialogPayload | null>(null)`):
    ```tsx
    type DialogPayload =
      | { kind: "send_recommended"; selections: BatchSelection[]; skipped: FailedPayment[] }
      | { kind: "send_specific"; selections: BatchSelection[]; emailType: SendableEmailType }
      | { kind: "mark_resolved"; rows: FailedPayment[] }
      | { kind: "exclude"; rows: FailedPayment[] };
    ```
    Render the dialog only when `payload !== null`. The Base UI Dialog primitive at `frontend/src/components/ui/dialog.tsx` handles focus trap, ESC-to-close, and return-focus-to-trigger automatically.
  - [x] 8.5 "Send recommended" handler: filter `selectedRows` by `recommended_email_type !== null`, derive `selections` (subscriber_id, failure_id, email_type=recommended). Pass both `selections` and the skipped list to the dialog so the dialog renders the "Skipped (no recommendation): K" section per AC #2. Disable the primary button when `selections.length === 0` (no rows have a recommendation — sensible no-op rather than dispatching an empty payload).
  - [x] 8.6 "Send specific" handler: secondary `<Button>` wrapped in `<DropdownMenuTrigger asChild>`. The dropdown lists the same 3 email-type options as Story 3.3's per-row dropdown, in the same order:
    ```tsx
    const SPECIFIC_OPTIONS: Array<{ type: SendableEmailType; label: string }> = [
      { type: "update_payment", label: "Update payment" },
      { type: "retry_reminder", label: "Retry reminder" },
      { type: "final_notice", label: "Final notice" },
    ];
    ```
    Selecting an option opens the dialog with `kind: "send_specific"` and ALL selected rows (filtered to status=`active` client-side, per AC #6) mapped to the chosen `emailType`.
  - [x] 8.7 Per-type rollup memoized in dialog body:
    ```tsx
    const rollup = selections.reduce<Record<string, number>>((acc, s) => {
      acc[s.email_type] = (acc[s.email_type] ?? 0) + 1;
      return acc;
    }, {});
    // Render: "Update Payment ×3 · Final Notice ×1"
    ```
  - [x] 8.8 Accessibility: header checkbox `aria-label="Select all visible rows"`. Per-row checkbox `aria-label={\`Select row for \${row.subscriber_email || row.subscriber_stripe_customer_id}\`}`. Selection-count line wrapped in `<span aria-live="polite" aria-atomic="true">`. Dialog title + description bound automatically by the Base UI primitive. Each toolbar button has an explicit `aria-label`.

- [x] **Task 9: Bulk fan-out hook for Mark resolved (N) + Exclude (N)** (AC: #11)
  - [x] 9.1 Create `frontend/src/hooks/useBulkFanout.ts`. Generic helper that issues per-row POSTs and aggregates the result. Single `invalidateQueries` after the entire fan-out settles:
    ```typescript
    "use client";

    import { useState, useCallback } from "react";
    import { useQueryClient } from "@tanstack/react-query";
    import api from "@/lib/api";

    type Endpoint = "mark-resolved" | "exclude";

    export interface BulkFanoutResult {
      succeeded: number;
      failed: number;
      total: number;
      failures: Array<{ subscriber_id: number; reason: string }>;
    }

    export function useBulkFanout(endpoint: Endpoint) {
      const queryClient = useQueryClient();
      const [isPending, setIsPending] = useState(false);
      const [lastResult, setLastResult] = useState<BulkFanoutResult | null>(null);

      const run = useCallback(
        async (subscriberIds: number[]): Promise<BulkFanoutResult> => {
          setIsPending(true);
          const settled = await Promise.allSettled(
            subscriberIds.map((id) =>
              api.post(`/subscribers/${id}/${endpoint}/`).then(() => id),
            ),
          );
          const failures: Array<{ subscriber_id: number; reason: string }> = [];
          let succeeded = 0;
          settled.forEach((res, i) => {
            if (res.status === "fulfilled") {
              succeeded += 1;
            } else {
              const reason = (res.reason as {
                response?: { data?: { error?: { message?: string } } };
              })?.response?.data?.error?.message ?? "Request failed.";
              failures.push({ subscriber_id: subscriberIds[i], reason });
            }
          });
          const result: BulkFanoutResult = {
            succeeded,
            failed: failures.length,
            total: subscriberIds.length,
            failures,
          };
          setLastResult(result);
          setIsPending(false);
          // Single invalidation after the whole fan-out settles.
          queryClient.invalidateQueries({ queryKey: ["failed-payments"] });
          queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
          return result;
        },
        [endpoint, queryClient],
      );

      return { run, isPending, lastResult };
    }
    ```
    `Promise.allSettled` is load-bearing — never short-circuits. A 422/429 on row 7 doesn't abort rows 8..50.

- [x] **Task 10: Wire selection state + new column into `FailedPaymentsList`** (AC: #1, #6, #10, #11)
  - [x] 10.1 Edit `frontend/src/components/dashboard/FailedPaymentsList.tsx`. Add selection state at the `FailedPaymentsList` level (where sort already lives): `const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());`. Key on `row.id` (failure id, NOT subscriber_id — a subscriber may have multiple failures in v2).
  - [x] 10.2 Insert a new leading `<TableHead>` and per-row `<TableCell>` containing the `Checkbox` primitive (`@/components/ui/checkbox`). Header checkbox is "select all rendered rows":
    - `checked = data.length > 0 && selectedIds.size === data.length`
    - `indeterminate = 0 < selectedIds.size && selectedIds.size < data.length` (Base UI's `Checkbox.Root` accepts `indeterminate` — verify against the primitive's props; if the project's wrapper at `components/ui/checkbox.tsx` doesn't expose it, set `data-state="indeterminate"` directly via a class workaround).
    - `onCheckedChange = (v) => setSelectedIds(v ? new Set(data.map((r) => r.id)) : new Set())`.
  - [x] 10.3 Per-row checkbox: `checked={selectedIds.has(row.id)}`, `onCheckedChange={(v) => setSelectedIds((prev) => { const next = new Set(prev); v ? next.add(row.id) : next.delete(row.id); return next; })}`. Free-tier: render the checkbox with `disabled` and `title={TIER_TOOLTIP}`. Force `selectedIds` empty for Free-tier (don't even mount the toolbar):
    ```tsx
    const effectiveSelectedIds = isFree ? new Set<number>() : selectedIds;
    ```
  - [x] 10.4 Compute `selectedRows = data?.filter((r) => effectiveSelectedIds.has(r.id)) ?? []` and pass to `<BulkActionToolbar selectedRows={selectedRows} ... />` rendered AFTER the `<Table>` (the toolbar is `position: fixed` so DOM order doesn't visually matter, but logical order is "table then floating UI" — keeps tab order sane).
  - [x] 10.5 Wire callbacks:
    - `onSendRecommended(selections, skipped)` → `batchSendEmail.mutate(selections, { onSuccess: handleBatchResult, onError: handleBatchError })`
    - `onSendSpecific(selections)` → same; the chosen type is already baked into `selections`
    - `onMarkResolved(rows)` → `markResolvedFanout.run(rows.map((r) => r.subscriber_id)).then(handleFanoutResult("Marked"))`
    - `onExclude(rows)` → `excludeFanout.run(rows.map((r) => r.subscriber_id)).then(handleFanoutResult("Excluded"))`
    - `onDeselectAll()` → `setSelectedIds(new Set())`
  - [x] 10.6 `handleBatchResult(res: BatchSendResult)` toast logic:
    - All queued + zero failed → `toast.success(\`Queued \${res.queued} dunning emails.\`)`
    - Mixed → `toast.warning(\`Queued \${res.queued} of \${res.selections_total}. \${res.failed} failed.\`, { duration: 8000 })`. If all failures share one code, append the human message; otherwise fall back to a generic "see audit log for details".
    - Zero queued → `toast.error("Could not queue any emails.", { duration: 6000 })`
    - Always call `setSelectedIds(new Set())` after a result to clear the bulk state.
  - [x] 10.7 `handleBatchError(err: SendEmailError)` mirrors Story 3.3's per-row error handling EXACTLY (same `RATE_LIMITED` / `OPT_OUT` / `EXCLUDED` / `DPA_REQUIRED` branching), but with rate-limit copy "Rate limit reached on bulk send. Try again in <N>s." (the rate-limit path here is a 429 from `_BatchSendEmailThrottle`, not from the per-row throttle).
  - [x] 10.8 `handleFanoutResult(verb: string)`:
    ```tsx
    const handleFanoutResult = (verb: "Marked" | "Excluded") => (res: BulkFanoutResult) => {
      if (res.failed === 0) {
        toast.success(`${verb} ${res.succeeded}.`);
      } else if (res.succeeded > 0) {
        toast.warning(`${verb} ${res.succeeded} of ${res.total} — ${res.failed} failed.`, { duration: 8000 });
      } else {
        toast.error(`Failed to ${verb.toLowerCase()} ${res.total}.`, { duration: 6000 });
      }
      setSelectedIds(new Set());
    };
    ```
  - [x] 10.9 Pending state: `isAnyBulkPending = batchSendEmail.isPending || markResolvedFanout.isPending || excludeFanout.isPending`. Pass to `<BulkActionToolbar isPending={isAnyBulkPending} pendingLabel={...} />`. While pending, ALL toolbar buttons disable. Per-row mutations from Story 3.3 v1 are independent — they have their own per-row pending state and remain interactive.
  - [x] 10.10 Subtle but load-bearing: `selectedIds` must clear when underlying `data` changes (sort or refetch returns different rows):
    ```tsx
    useEffect(() => {
      setSelectedIds(new Set());
    }, [data]);
    ```
    Without this, a sort change leaves a stale selection that may include rows no longer in view. (To preserve selection across re-renders of the SAME data, the dev could intersect `selectedIds` with `data.map(r => r.id)` instead — but the simpler "clear on data identity change" is correct for v1.)
  - [x] 10.11 The existing per-row `ActionButtons` column stays unchanged — Story 3.4 v1 ADDS the leading checkbox column and the toolbar; it does NOT modify per-row controls.

- [x] **Task 11: Settings change for `mark_resolved` throttle bump** (AC: #11)
  - [x] 11.1 Edit `backend/safenet_backend/settings/base.py:104-110`. Change `"mark_resolved": "10/min"` → `"mark_resolved": "60/min"`. Inline rationale comment:
    ```python
    "mark_resolved": "60/min",  # Story 3.4 v1 — bumped from 10/min to support bulk Mark resolved (N) fan-out (≤50 rows)
    ```
    Safe: `mark_resolved` has zero external side effect (no email, no Stripe call) — it's a DB FSM transition + audit write. The 10/min limit was a defense against accidental UI spam; 60/min still defends against runaway scripts while accommodating realistic batches.

- [x] **Task 12: Frontend tests — `useBatchSendEmail` hook** (AC: #3, #5)
  - [x] 12.1 Create `frontend/src/__tests__/useBatchSendEmail.test.ts`. Mirror `useSendEmail.test.ts:1-80` shape — `vi.mock("@/lib/api")`, `makeAxiosError` helper, `QueryClientProvider` wrapper:
    - `posts to /subscribers/batch-send-email/ with selections array` — assert request body shape `{selections: [...]}`.
    - `returns BatchSendResult on success` — happy path, `result.current.data.queued === 3`.
    - `surfaces partial failures verbatim` — response body has `failures: [{subscriber_id, failure_id, code:"OPT_OUT", message}]`. Assert exposed on `result.current.data.failures[0]`.
    - `wraps 429 into SendEmailError with retryAfterSeconds` — same shape as `useSendEmail` 429 test. `Retry-After: "42"` parses to `42`.
    - `wraps 403 DPA_REQUIRED into SendEmailError`.
    - `invalidates failed-payments and dashboard summary on success` — spy on `queryClient.invalidateQueries`, assert called with both query keys.
    - `null retry-after header parses as null retryAfterSeconds`.

- [x] **Task 13: Frontend tests — `BulkActionToolbar` component + `FailedPaymentsList` selection** (AC: #1, #2, #6, #10, #11)
  - [x] 13.1 Create `frontend/src/__tests__/BulkActionToolbar.test.tsx`. Reuse the `vi.mock("@/components/ui/dropdown-menu")` passthrough block from `frontend/src/__tests__/FailedPaymentsList.test.tsx:74-108` — Radix `DropdownMenuItem`'s `onSelect` cannot be triggered via `fireEvent.click` in jsdom without it. Tests:
    - `renders nothing when selectedRows is empty` — `screen.queryByRole("toolbar")` returns null.
    - `renders 4 buttons + deselect link in correct order with N selected` — query each by `aria-label`.
    - `Send recommended button is disabled when zero rows have a recommendation` — selectedRows all have `recommended_email_type === null`. Button has `disabled`.
    - `clicking Send recommended opens confirmation dialog with per-row summary` — render with 3 rows (2 update_payment, 1 null). Click. Assert dialog opens (`getByRole("dialog")`), lists 2 selections, lists 1 in skipped, rollup line "Update Payment ×2".
    - `clicking Confirm dispatches onSendRecommended with filtered selections` — assert callback args = `[{...}, {...}]` (2 entries, no skipped).
    - `clicking Cancel returns focus to trigger button without dispatching` — focus assertion via `document.activeElement`.
    - `Send specific dropdown opens then dialog with all rows mapped to chosen type` — dropdown menuitem click → dialog opens → confirm → callback called with all selections mapped to chosen type.
    - `Mark resolved opens "Mark N as resolved?" confirm dialog` — dialog title text.
    - `Exclude opens "Exclude N from future recommendations?" dialog`.
    - `Deselect all link calls onDeselectAll`.
    - `selection-count line has aria-live="polite"`.
    - `disables all 4 toolbar buttons when isPending=true`.
  - [x] 13.2 Edit `frontend/src/__tests__/FailedPaymentsList.test.tsx`. Add hoisted mocks for the new hooks alongside the existing block:
    ```typescript
    const {
      // ... existing refs ...
      mockUseBatchSendEmail,
      mockBatchSendMutate,
      mockUseBulkFanout,
      mockMarkResolvedFanoutRun,
      mockExcludeFanoutRun,
    } = vi.hoisted(() => {
      const refs = {
        // ... existing ...
        mockUseBatchSendEmail: vi.fn(),
        mockBatchSendMutate: vi.fn(),
        mockUseBulkFanout: vi.fn(),
        mockMarkResolvedFanoutRun: vi.fn(),
        mockExcludeFanoutRun: vi.fn(),
      };
      return refs;
    });

    vi.mock("@/hooks/useBatchSendEmail", async () => {
      const actual = await vi.importActual<typeof import("@/hooks/useBatchSendEmail")>(
        "@/hooks/useBatchSendEmail",
      );
      return { ...actual, useBatchSendEmail: () => mockUseBatchSendEmail() };
    });
    vi.mock("@/hooks/useBulkFanout", () => ({
      useBulkFanout: (endpoint: string) => mockUseBulkFanout(endpoint),
    }));
    ```
    Default mock implementations in `beforeEach`:
    ```typescript
    mockUseBatchSendEmail.mockReturnValue({ mutate: mockBatchSendMutate, isPending: false });
    mockUseBulkFanout.mockImplementation((endpoint: string) => ({
      run: endpoint === "mark-resolved" ? mockMarkResolvedFanoutRun : mockExcludeFanoutRun,
      isPending: false,
      lastResult: null,
    }));
    ```
    New tests:
    - `renders leading checkbox column for paid Mid-tier with DPA accepted`.
    - `selecting a row reveals BulkActionToolbar` — click checkbox, `getByRole("toolbar")` returns the toolbar.
    - `header checkbox toggles select-all of rendered rows`.
    - `Free-tier checkboxes are disabled with tier tooltip` — `.toHaveAttribute("title", "Upgrade to Mid or Pro to enable email actions")`.
    - `Free-tier never renders BulkActionToolbar even after click` — checkbox is disabled; `queryByRole("toolbar")` stays null.
    - `sort change clears selection` — set selection (mock data unchanged), trigger a sort header click (changes `data` reference because the mock returns a new array), assert toolbar disappears.
    - `Send recommended dispatches via useBatchSendEmail with filtered selections` — assert `mockBatchSendMutate.mock.calls[0][0]` shape.
    - `Mark resolved bulk fans out via useBulkFanout("mark-resolved")` — `mockMarkResolvedFanoutRun.toHaveBeenCalledWith([id1, id2, id3])`.
    - `Exclude bulk fans out via useBulkFanout("exclude")`.
    - `Successful batch surfaces toast.success and clears selection` — drive `mockBatchSendMutate` to invoke `onSuccess` with a happy result, assert `mockToastSuccess` called with the expected message and `selectedIds` is empty (toolbar disappears).
    - `Partial batch failure surfaces toast.warning with count breakdown`.
    - `429 batch error surfaces toast.error with retry-after seconds` — invoke `onError` with `new SendEmailError({code:"RATE_LIMITED",...}, 429, "42")`, assert `mockToastError` called with the expected text.
  - [x] 13.3 Run `cd frontend && pnpm vitest run BulkActionToolbar useBatchSendEmail FailedPaymentsList` — all green.

### Cross-cutting

- [ ] **Task 14: Manual smoke verification** (AC: all) — _Deferred to reviewer; the automated suite covers ACs 1–11._
  - [ ] 14.1 `docker compose up`. Seed a Mid-tier account with DPA accepted (use the seed user from 3-1-v1's manual verification). Seed at least 5 SubscriberFailures across multiple subscribers. Optionally pre-create a `NotificationOptOut` row for one subscriber to exercise partial-failure path.
  - [ ] 14.2 In the browser:
    - Open `/dashboard`. Tick 3 row checkboxes → toolbar slides up with "Send recommended (3)".
    - Click "Send recommended (3)" → dialog shows per-row summary + per-type rollup. Confirm → success toast "Queued 3 dunning emails." → selection clears.
    - Tick 2 rows including the opted-out subscriber → "Send recommended (2)" → mixed warning toast "Queued 1 of 2. 1 failed.".
    - Click "Send specific…" → dropdown lists 3 options → pick "Final notice" → dialog shows all selected rows mapped to "Final notice" → confirm.
    - Trigger 6 batches in 60s (DevTools console loop) → 6th surfaces "Rate limit reached on bulk send. Try again in <N>s.".
    - Tick 5 rows → "Mark resolved (5)" → confirm → success toast.
    - Tick 5 rows → "Exclude (5)" → confirm → success toast.
  - [ ] 14.3 Polling smoke (shell access required to manipulate Stripe Mock or fixtures):
    - Trigger `poll_account_failures.delay(account.id)` directly via `docker compose exec -T web poetry run python manage.py shell`. Confirm an Active subscriber whose mocked Stripe sub is `canceled` transitions to `passive_churn`.
    - Set a SubscriberFailure's PI to `succeeded` in Stripe Mock. Re-trigger poll. Confirm Active → Recovered + recovery confirmation email enqueued.
  - [ ] 14.4 Switch user's tier to `free` via shell → confirm leading checkbox column is disabled with tier tooltip; toolbar never appears. `curl POST /api/v1/subscribers/batch-send-email/` directly returns `403 TIER_REQUIRED`.

### Review Findings

#### Decisions resolved

- [x] [Review][Decision-resolved] **D1: Toolbar button DOM order** — kept right-anchored (primary CTA on the right). Common bulk-bar convention; tests are aria-label-based and pass either way. No change needed.

#### Patches

- [x] [Review][Patch] Confirmation dialog body shows `subscriber #<id>` instead of subscriber email/customer-id — violates AC #2 ("per-row summary list of subscriber email + recommended-email label"). `mark_resolved`/`exclude` dialogs use `subscriberDisplay(row)` correctly; `send_recommended`/`send_specific` do not. Also remove dead `const row = […].find((_) => true); void row;` artifact at the same site. [`frontend/src/components/dashboard/BulkActionToolbar.tsx:127-137, 156-160`]
- [x] [Review][Patch] Bulk fan-out duplicates `subscriber_id` when one subscriber has multiple selected failures — `selectedIds` keys on `failure.id` but `onMarkResolvedBulk`/`onExcludeBulk` map to `subscriber_id` without dedup. Two POSTs to the same subscriber's endpoint; second hits `INVALID_STATE`. [`frontend/src/components/dashboard/FailedPaymentsList.tsx:477-487`]
- [x] [Review][Patch] Header checkbox missing `indeterminate` visual state per Task 10.2. Pass `indeterminate={selectedRows.length > 0 && selectedRows.length < allRendered}` to the header `Checkbox` (Base UI primitive accepts the prop). [`frontend/src/components/dashboard/FailedPaymentsList.tsx:533-540`]
- [x] [Review][Patch] `useBulkFanout` drops per-row error `code` (only stringifies `message`); UX cannot distinguish OPT_OUT vs RATE_LIMITED vs EXCLUDED in partial-failure toasts. Extend `BulkFanoutFailure` with `code` and `status` and parse from `response.data.error.code` + `response.status`. [`frontend/src/hooks/useBulkFanout.ts:9-12, 34-44`]
- [x] [Review][Patch] Bypass-mode test coverage gap — only Gate 2 (`no_email`) is verified for `send_recovery_confirmation(bypass_engine_active=True)`. Add three tests under `TestSendRecoveryConfirmation` matching the pattern of `test_bypass_does_not_skip_other_gates`: `excluded_from_automation` (Gate 3), `opt_out` (Gate 4), and `duplicate` `NotificationLog` row already at `status="sent"` (Gate 5). [`backend/core/tests/test_tasks/test_notifications.py:523-565`]
- [x] [Review][Patch] `useBulkFanout` calls `setIsPending(false)` before `invalidateQueries` — microtask race window where a re-click sees `isPending=false` while a refetch is in flight. Reorder: invalidate first, then clear pending. [`frontend/src/hooks/useBulkFanout.ts:53-56`]
- [x] [Review][Patch] `failure_id` audit metadata typed inconsistently across this story — `_check_payment_recoveries` writes `str(failure.id)`, `batch_send_email` writes raw `int`. Pick one (project history uses `str()` in audit metadata). [`backend/core/views/batch_send_email.py:222, 234`, `backend/core/tasks/polling.py:496`]
- [x] [Review][Patch] Hardcoded `from core.tasks.notifications import send_recovery_confirmation` import inside the per-failure `for` loop in `_check_payment_recoveries`. Hoist to the top of the function (or module top) — circular-import risk is what motivated the local import in v0, but `_check_payment_recoveries` is new and no longer imported by `notifications.py`. [`backend/core/tasks/polling.py:503`]
- [x] [Review][Patch] (D2) Extend client-side filtering to "Send recommended" — `deriveRecommended` should drop rows where `subscriber_status !== "active"` or `excluded_from_automation === true`, mirroring `deriveSpecific`'s active-filter. Without this, Send-recommended on a selection containing recovered/excluded rows produces confusing per-row failure toasts. Update the dialog to surface a "Skipped (not eligible): K" tally alongside the existing "Skipped (no recommendation): K" line. [`frontend/src/components/dashboard/BulkActionToolbar.tsx:58-76, 117-148`]
- [x] [Review][Patch] (D3) Disable dropdown items in "Send specific…" when `deriveSpecific(selectedRows, opt.type)` returns an empty list — current behavior opens an empty `Send 0 X emails?` dialog with a disabled primary. Compute eligibility per option and pass `disabled` to each `<DropdownMenuItem>`; if zero rows are eligible across all three types, the dropdown trigger itself should disable. [`frontend/src/components/dashboard/BulkActionToolbar.tsx:285-316`]
- [x] [Review][Patch] (D4) Wrap the per-row `send_dunning_email.delay()` call in a try/except for broker `OperationalError` — record as `failures[{code: "QUEUE_ERROR", message: "Could not enqueue email send."}]` instead of bubbling out and aborting the batch. The summary audit row should still write with the partial outcome. [`backend/core/views/batch_send_email.py:213-227`]
- [x] [Review][Patch] (D5) Add explicit `selectedIds` pruning when `data` identity changes (sort, refetch dropping rows) — intersect `selectedIds` with the new `data` row-id set so the Set itself doesn't accumulate stale ids. Pair with a regression test in `FailedPaymentsList.test.tsx` that selects rows, triggers a sort change that returns a different row set, and asserts the toolbar disappears (or count updates correctly). The header `indeterminate` patch (above) covers the visual side; this finding covers the data side. [`frontend/src/components/dashboard/FailedPaymentsList.tsx:393-402`, `frontend/src/__tests__/FailedPaymentsList.test.tsx`]

#### Deferred (pre-existing or out-of-scope)

- [x] [Review][Defer] No `_audit_blocked` row written for batch `NOT_FOUND` lookups — same pattern as per-row `send_email`; security hardening for v2. [`backend/core/views/batch_send_email.py:159-180`] — _Reason: matches existing convention; pre-existing posture._
- [x] [Review][Defer] `useBulkFanout` issues unbounded parallel POSTs (no client-side cap or chunking) — `mark_resolved` at 60/min could be exhausted by a single 60+ row fan-out. v1 traffic is bounded by current-month dashboard so unlikely in practice. [`frontend/src/hooks/useBulkFanout.ts:26-46`] — _Reason: v2 scaling concern._
- [x] [Review][Defer] `_check_payment_recoveries` silently skips on Stripe `RateLimitError` (caught as generic `StripeError`); should retry distinctly. Same pattern as `_check_subscription_cancellations`. [`backend/core/tasks/polling.py:457-466`] — _Reason: matches existing helper's posture; revisit alongside polling-resilience hardening._
- [x] [Review][Defer] `_check_payment_recoveries` walks every Active subscriber even with zero failures (no `EXISTS` pre-filter). [`backend/core/tasks/polling.py:441-454`] — _Reason: v2 perf optimization; v1 subscriber count is bounded._
- [x] [Review][Defer] `request.user.__class__.account.RelatedObjectDoesNotExist` is a fragile attribute-traversal pattern; explicit `Account.DoesNotExist` would be cleaner. Mirrors per-row `send_email` view. [`backend/core/views/batch_send_email.py:49-55`] — _Reason: matches existing convention._
- [x] [Review][Defer] `test_no_account_returns_404` removed per Dev Agent Record (FK name mismatch); the 404 branch in the view is now untested. [`backend/core/views/batch_send_email.py:49-55`] — _Reason: defensive corner case beyond AC #1–#11; per-row `send_email` has no equivalent test either._

## Dev Notes

### v1 Scope Boundaries (READ FIRST)

- **In scope:**
  - New `POST /api/v1/subscribers/batch-send-email/` view — validates a list of selections, fans out per-selection enqueues via `send_dunning_email.delay`, returns partial-failure shape.
  - New `_BatchSendEmailThrottle` (5/min) + `batch_send_email` scope in `DEFAULT_THROTTLE_RATES` + per-scope throttled-message entry.
  - Polling task changes: `_check_subscription_cancellations` lifted out of `is_engine_active` gate; new `_check_payment_recoveries` helper for Active → Recovered detection + Story 4.3's recovery confirmation dispatch.
  - `send_recovery_confirmation` task gains `bypass_engine_active` kwarg (parallel to Story 3.3 v1's `send_dunning_email`); v1 polling caller passes `True`.
  - Frontend: leading checkbox column + select-all header + `BulkActionToolbar` floating fixed-bottom + confirmation dialog + bulk send hook (`useBatchSendEmail`) + bulk fan-out hook (`useBulkFanout`) for Mark resolved (N) + Exclude (N).
  - Throttle bump on `mark_resolved` from 10/min → 60/min to support bulk fan-out.
- **Out of scope:**
  - Bulk Mark resolved + Bulk Exclude as **backend bulk endpoints** — kept as client-side fan-outs over existing per-row endpoints. The `/batch-send-email/` endpoint is the only new bulk backend surface (per `sprint-change-proposal-2026-04-29.md §2e`).
  - Card-update detection (`_detect_card_updates`) — stays gated behind `is_engine_active` (effectively quarantined for v1 since `engine_mode=None`).
  - PendingAction supervised-queue model + `actions.py`'s `batch_approve_actions` — quarantined v0; pattern-reference only.
  - Recovery email content / templates — owned by Story 4.3; this story only changes the trigger path.
  - Recommendation rule engine populating `recommended_email_type` — Story 3.5 v1. Until 3.5 lands, "Send recommended (N)" silently filters every row out (the dialog's Skipped section becomes the entire selection); the Send button disables when filtered list is empty. Test the empty-filtered-payload no-dispatch path explicitly (Task 13.1).
  - Per-account timezone in dashboard month boundary — still UTC, deferred from 3.2 v1.
  - Persisting selection across navigation — selection state is component-local; route changes wipe it.
  - "Undo within 60 seconds" (mentioned in sprint-change-proposal §4.1 Edit 9 risk-mitigation) — out of scope; the confirm dialog is the safety net.

### Architecture Compliance

- **Tenant isolation:** all queries via `for_account(account.id)` from `TenantScopedModel.objects` (`models/base.py:13-15`). The batch view's `_process_one_selection` MUST scope each lookup; never `.objects.all()` even in a small batch. [Source: architecture.md#Enforcement Guidelines:594-610]
- **API response envelope:** `{"data": ...}` for success (including partial-failure `{data: {queued, failed, failures, selections_total}}`), `{"error": {code, message, field}}` for full rejections. The presence of partial failures inside `data.failures` does NOT flip the response to an error envelope — partial failure is a successful API call with mixed per-row outcomes. [Source: architecture.md#Format Patterns:489-510]
- **Field naming:** snake_case in API + TS interfaces. `subscriber_id`, `failure_id`, `email_type`, `selections_total`. No camelCase. [Source: architecture.md#Naming Patterns:415-427]
- **API URL pattern:** kebab-case multi-word: `/batch-send-email/`. [Source: architecture.md#Naming Patterns:410]
- **DPA gate first:** the batch view calls `require_dpa_accepted(account)` BEFORE any tenant scoping or body validation, per `services/dpa.py:25-43` docstring and 3-1-v1 / 3-3-v1 contract. A malformed payload from an unsigned account returns `DPA_REQUIRED`, NOT `VALIDATION_ERROR`. [Source: 3-1-v1-dpa-acceptance-gate.md AC1]
- **Error handling by layer:** view returns DRF Response with envelope; the custom exception handler at `core/views/errors.py:25-47` maps `Throttled` → `RATE_LIMITED` envelope. The new `batch_send_email` scope's message is added to `_THROTTLED_MESSAGES`. The frontend axios layer is the same; `useBatchSendEmail` reuses Story 3.3's `SendEmailError` wrapper for code/retryAfterSeconds extraction. [Source: architecture.md#Process Patterns:570-590]
- **TanStack Query mutations invalidate.** Both `useBatchSendEmail` and `useBulkFanout` invalidate `["failed-payments"]` + `["dashboard","summary"]` on completion, matching Story 3.3 v1's `useSendEmail` / `useMarkResolved` / `useExcludeSubscriber`.
- **No business logic in views beyond gating + dispatch.** The batch view gates + per-selection-validates + enqueues + audits. The `send_dunning_email` Celery task owns delivery. [Source: architecture.md#Structure Patterns:477]
- **Audit-event verbs (Story 3.4 v1 introductions):**
  - `batch_email_send` — one summary row per request: actor=client, outcome=success|partial|failed, metadata.queued, metadata.failed, metadata.trigger=`client_manual`.
  - `payment_success_detected` — engine, polling-driven Active → Recovered detection event (separate from the post_transition signal's `status_recovered`).
  Existing verbs unchanged but extended:
  - `email_sent` rows for batch dispatches add `metadata.batch=true`.
  - `notification_sent` rows from polling-recovery dispatch add `metadata.trigger="polling_recovery"`.
  `AuditLog.action` is a free-form CharField, so no migration or enum update required.
- **Celery task idempotency:** the partial unique constraint on NotificationLog `(failure, email_type) WHERE status="sent"` is the source of truth. A duplicated batch (same selection submitted twice) results in `duplicate_race` suppressions on the second attempt — same pattern as Story 3.3 v1.

### Technical Requirements

- **`is_engine_active` is now half-relevant.** v0 callers (`send_failure_notification`, `send_final_notice`, `send_recovery_confirmation` v0 path, `_detect_card_updates`, `_process_supervised_queue`, `_process_autopilot_recovery`, `_process_unqueued_failures`) still gate on it — keep their behavior unchanged. v1 callers (the new `_check_subscription_cancellations` ungated call, `_check_payment_recoveries`, the `send_recovery_confirmation` dispatch with bypass=True) explicitly opt out. **DO NOT** remove `is_engine_active` in this story; the Sprint Change Proposal §3.2 quarantine pass owns that cleanup.
- **Batch-send view does NOT pre-deduplicate.** A batch with two entries for the same `(failure_id, email_type)` results in two `delay()` calls and two `email_sent` audit rows; the second `send_dunning_email` task execution catches the IntegrityError on NotificationLog and writes a `duplicate_race` suppression. Pre-dedup at the view would obscure the user's actual click count from the audit trail.
- **Throttle scoping.** `_BatchSendEmailThrottle` extends `SimpleRateThrottle`, NOT `ScopedRateThrottle` (Story 3.3 v1 debug log captured why DRF's `ScopedRateThrottle` silently no-ops on `@api_view` function views — `view.throttle_scope` is None). Cache key format: `f"throttle_batch_send_email_{user.pk}"`. Rate `5/min` → 5 batches per 60s per user. Reasoning: batch size up to 100; 5 batches = 500 enqueues/min ceiling — generous for v1 traffic but bounded against runaway loops.
- **Per-row vs batch throttle independence.** A user who already exhausted `send_email` (10/min on `/send-email/`) can still fire a `/batch-send-email/` request — the two scopes are distinct cache keys. This is intentional: a per-row send and a batch send are different intentions with different ergonomics.
- **N+1 Stripe call concern in `_check_payment_recoveries`** is real but accepted for v1. Per the sprint change proposal `deferred-work.md` annotation, "story-3-2 review" already documents N+1 in `_check_subscription_cancellations` as deferred. Same call pattern, same deferral. Stripe has no batch `PaymentIntent.retrieve(id__in=[...])`, so per-PI retrieval is the simplest correct implementation. Optimization belongs to v2.
- **`_check_payment_recoveries` ordering by `failure_created_at` ASC** is intentional. If a subscriber has 3 failures (March, April, May) and Stripe reports March's PI as succeeded, March's failure drives the recovery confirmation email. v1 doesn't support per-failure recovery emails — one Subscriber transition Active → Recovered = one recovery email. Picking the oldest matches "the case Marc has been worrying about longest just resolved".
- **`select_for_update()` in `_check_payment_recoveries`'s atomic block** prevents a race with `mark_resolved_manually` from Story 3.3 (which uses the same lock pattern). If the user manually resolves between the first PI fetch and the FSM transition, the lock serializes them and the second arrival sees `status != STATUS_ACTIVE` and bails.
- **Recovery confirmation email gating in v1:**
  - The v1 polling recovery path dispatches `send_recovery_confirmation.delay(failure.id, bypass_engine_active=True)` ONLY when `account.tier in (TIER_MID, TIER_PRO) and account.dpa_accepted`. Free-tier and unsigned-DPA accounts get the FSM transition (so the dashboard reflects truth) but no email.
  - The task's Gate 1 bypass is the `bypass_engine_active=True` kwarg. Gates 2–6 still run inside `_passes_gates` — particularly Gate 4 (opt_out) and Gate 5 (duplicate-NotificationLog-row). A subscriber who opted out gets no recovery email; a duplicate dispatch is gracefully suppressed.
  - Audit metadata distinguishes v1 polling-driven (`trigger="polling_recovery"`) from v0 retry-success-driven (no `trigger` key) so post-hoc analysis attributes confirmation emails to the right source.
- **Frontend: `useFailedPayments` `staleTime: 5 * 60 * 1000` + `refetchInterval: 5 * 60 * 1000`** means a successful bulk action invalidates the cache and triggers an immediate refetch (TanStack Query default behavior on `invalidateQueries`). The toolbar's "selection clears after action" behavior is implemented via `setSelectedIds(new Set())` in the result handlers — NOT via cache invalidation alone, because the user may have selected rows the refetch still returns (rows that haven't been dispatched-then-recovered yet).
- **Free-tier guard on the frontend:** the leading checkbox column header always renders (sr-only label), but Free-tier users see disabled checkboxes with the tier tooltip. The toolbar literally never mounts (rendered with `selectedRows={[]}` because Free-tier `toggleId` is a no-op via the `isFree`-aware `effectiveSelectedIds`). Identical to the Story 3.3 v1 pattern of "render the control, gate via disabled+tooltip".
- **`Promise.allSettled` semantics in `useBulkFanout`** are load-bearing: never short-circuits, so a 422 or 429 on row 7 doesn't abort rows 8..50. Each settled result maps to a `failures` entry. Post-fanout `invalidateQueries` runs ONCE.
- **Asymmetry NOT to "fix":** the **view-level** opt-out check uses `NotificationOptOut.objects.for_account(account.id).filter(...)` (tenant-scoped). The **Gate 4** lookup inside `_passes_gates` (`backend/core/tasks/notifications.py:72-77`) uses bare `.filter(account=account)` — NOT scoped via `for_account`. Both are correct in context (the task already received an `account`-bound failure object). A dev who notices the inconsistency may be tempted to swap Gate 4 to `for_account` and break `test_optout.py` assertions. **Leave Gate 4 as-is.** Story 3.4 does NOT modify `_passes_gates` body — it only extends `send_recovery_confirmation`'s kwargs (Task 3.2).
- **Existing tests for backend run inside Docker.** Per project memory, `docker compose exec -T web poetry run pytest …` is the convention; the `db` hostname only resolves inside the docker network. Do NOT run pytest from the host.

### UX Design Requirements

- **Toolbar position.** Fixed bottom, full-width content area at max-width `1280px`, `z-50`, `border-t`, `bg-[var(--bg-surface)]`, `shadow-lg`. Mirror visual tokens from `frontend/src/components/review/BatchActionToolbar.tsx:23-26` (the v0 quarantined component) — internal-style consistency only; do NOT import. [Source: ux-design-specification.md#BatchActionToolbar:963-979]
- **Button hierarchy.** Primary `Send recommended (N)` uses `variant="default"` (filled — visual anchor). Secondary `Send specific…` uses `variant="outline"`. Tertiary `Mark resolved (N)` and `Exclude (N)` use `variant="ghost"`. Deselect-all is a plain text link (NOT a Button), matching the v0 toolbar's underline-on-hover affordance. [Source: ux-design-specification.md#12.1:1052-1056 — "Batch action bar uses a single Primary"]
- **Selection-count copy.** Singular vs plural: `1 row selected` vs `N rows selected`. Use the same conditional ternary as the v0 toolbar (`selectedCount !== 1 ? "s" : ""`).
- **Confirmation dialog copy.**
  - Send recommended: title `Send {N} dunning emails?` — body lists each row's `subscriber_email · email_type_label`, then per-type rollup ("Update Payment ×3 · Final Notice ×1"), then "Skipped (no recommendation): K" if any. Primary `Send all`.
  - Send specific: title `Send {N} {email_type_label} emails?` — body lists each row's subscriber_email (no per-row email_type since uniform). Primary `Send all`.
  - Mark resolved: title `Mark {N} as resolved?` — body lists each row's subscriber_email · current status. Primary `Mark resolved`.
  - Exclude: title `Exclude {N} from future recommendations?` — body lists subscriber_emails. Primary `Exclude all`.
  - Cancel button label: `Cancel` (variant=outline) on every dialog.
- **Pending state in dialog.** While the mutation is in flight, the primary button label changes to "Sending…" / "Marking resolved…" / "Excluding…" and is disabled. Cancel stays enabled (clicking cancel during in-flight is a no-op for the network — request continues, dialog closes, toast still surfaces on completion).
- **Toast policy.**
  - Success: `toast.success` (sonner default duration ~4s).
  - Partial: `toast.warning` (`duration: 8000` — long enough to read partial-failure breakdown).
  - Full failure: `toast.error` (`duration: 6000`).
  - Rate-limit: `toast.error` with retry-after seconds inline (`duration: 6000`).
  - Blocking error (DPA missing): `duration: Infinity`. Mirrors Story 3.3 v1's per-row durations exactly.
- **Accessibility.**
  - Toolbar: `role="toolbar"`, `aria-label="Bulk actions"`. [Source: ux-design-specification.md#BatchActionToolbar:978]
  - Selection count: wrapped in `aria-live="polite" aria-atomic="true"`.
  - Header checkbox: `aria-label="Select all visible rows"`. Per-row checkbox: `aria-label={\`Select row for \${row.subscriber_email || row.subscriber_stripe_customer_id}\`}`.
  - Dialog: Base UI Dialog handles focus trap + ESC + return-focus automatically. `<DialogTitle>` and `<DialogDescription>` provide the `aria-labelledby` / `aria-describedby` bindings.
- **Free-tier UX.** Leading checkbox column header still renders (sr-only label), but every row checkbox has `disabled` + `title={TIER_TOOLTIP}`. Pre-existing inline upgrade banner (Story 3.2 v1) above the table remains the primary CTA. Toolbar never appears.
- **Don't surface the polling status detection.** AC #7 + #8 are backend-only; no UI affordance needs to communicate "your subscriber transitioned to Passive Churn via polling". The dashboard refetches and the badge changes. Future stories (UX-DR5 PollingStatusIndicator from epics.md:120) communicate poll cadence; this story does NOT add such an indicator.

### Previous Story Intelligence

From Story 3-3-v1 (per-row send + manual resolve, just shipped):
- **`SendEmailError` envelope wrapper is the canonical error type for client-triggered email mutations.** `useBatchSendEmail` reuses it directly; consumers branch on `code` ("RATE_LIMITED" / "OPT_OUT" / "EXCLUDED" / "DPA_REQUIRED" / unknown) with the same toast-and-duration mapping.
- **`SimpleRateThrottle` subclass with explicit `get_cache_key`** is the canonical pattern. `_BatchSendEmailThrottle` mirrors `_SendEmailThrottle` exactly. Do NOT reach for `ScopedRateThrottle` — DRF's `ScopedRateThrottle.allow_request` overwrites `self.scope` from `view.throttle_scope` (None on `@api_view` function views), silently no-opping the throttle.
- **`_passes_gates(bypass_engine_active=False)` kwarg** is the v1 escape hatch. Story 3.3 added it on `send_dunning_email`; Story 3.4 adds the same kwarg passthrough on `send_recovery_confirmation`. Two callers with explicit bypass + N existing callers with default-False = no v0 regression.
- **Throttle test pattern.** `cache.clear()` autouse fixture per test file resets DRF throttle state. The `Retry-After` header DRF sets automatically on `Throttled` exceptions; tests assert its presence as a positive int string.
- **Tenant isolation at the view layer.** Other-tenant lookups return 404 via `for_account(...).get(...)` raising `DoesNotExist`. Batch view's per-selection lookup follows this — a malformed batch with a foreign-tenant subscriber_id surfaces as `failures: [{code: "NOT_FOUND"}]`, not as a tenant-leak.
- **Dropdown menu test mock.** Radix `DropdownMenuItem` `onSelect` cannot be triggered via `fireEvent.click` in jsdom. Reuse the `vi.mock("@/components/ui/dropdown-menu")` passthrough block from `frontend/src/__tests__/FailedPaymentsList.test.tsx:74-108` — copy verbatim. New `BulkActionToolbar.test.tsx` will need the same mock for the "Send specific" dropdown.
- **`<Toaster />` is mounted in providers.tsx.** Bulk toasts use `toast.success/warning/error` directly without ceremony. `richColors` + `position="top-right"` is set globally; do NOT pass these per-call.
- **TanStack Query v5: `mutation.isPending` (NOT `isLoading`).** `mutate(vars, {onSuccess, onError})` for per-call callbacks. `mutation.variables` exposes the in-flight call's variables (used by Story 3.3 v1 for the "Sending…" per-row label; not needed in this story since the toolbar pending state is binary).
- **Loading-state default.** While ANY of `useBatchSendEmail`/`useBulkFanout(mark)`/`useBulkFanout(exclude)` is pending, ALL toolbar buttons disable. Per-row controls (Story 3.3 wiring) are independent — they have their own per-row pending state.

From Story 3-2-v1 (current-month dashboard):
- **`["failed-payments"]` query key is canonical.** Bulk hooks invalidate this key + `["dashboard", "summary"]`. Single string `["dashboard-summary"]` would silently no-op — see `frontend/src/hooks/useDashboardSummary.ts:10` for the canonical two-element form.
- **Free-tier upgrade banner pattern.** The inline banner above the table (Story 3.2 v1's Task 6.3) covers the upgrade CTA; the bulk toolbar does NOT need its own upgrade affordance — disabled checkbox + tier tooltip is the gate.
- **Native `title` attribute is the project's tooltip surface.** No `@base-ui/react` Tooltip — Story 3-2-v1 deferred that. Tests assert via `getAttribute("title")`.

From Story 4.3 (recovery confirmation email):
- **`send_recovery_confirmation_email(subscriber, failure, account)`** is the email-builder service entry point — synchronous, raises `SkipNotification` / `EmailConfigurationError` / `Exception`. The Celery task wraps with retry/DLL machinery. `bypass_engine_active=True` from the polling caller does NOT alter this path — it only skips Gate 1 inside `_passes_gates`. Synchronous send + NotificationLog write + audit emit are unchanged.
- **NotificationLog dedup constraint** spans both v0 (retry-driven) and v1 (polling-driven) paths. A subscriber whose retry-success path AND polling-recovery path both fire (extremely unlikely under v1 since v0 retry is quarantined) would produce one `sent` row and one `duplicate_race` suppression.

From Story 2.2 (90-day retroactive scan):
- **`failure_created_at` semantics.** Pulled from Stripe's `payment_intent.created` timestamp, stored UTC. The 90-day lookback in `_check_payment_recoveries` is a Django `__gte` on this field — no timezone conversion needed.

### Git Intelligence

Recent commits (`git log --oneline -8`):
- `1d1c58f` Status: done — sprint-status update for Story 3.3 v1.
- `4a592ad` Merge pull request #3 (Story 3.3 v1 done).
- `8a647d0` Status: done — sprint-status update for Story 3.2 v1.
- `01e1026` Merge pull request #2 (Story 3.1 v1 done).
- `7f270c4` Status: done — sprint-status update for Story 3.1 v1.

**Implication:** All v1 prerequisites are merged. Story 3.4 builds directly on the patterns and infrastructure from 3-1-v1 (DPA gate), 3-2-v1 (failed-payments dashboard), and 3-3-v1 (per-row send + manual resolve). The v0 polling code (`_check_subscription_cancellations`, `_detect_card_updates`, `_process_*` helpers) is on `main` but mostly inactive for v1 accounts; this story selectively activates the cancellation helper and adds the new recovery helper. Quarantined `actions.py` `batch_approve_actions` is NOT a model for this story — its API shape (`{action_ids: [...]}` + per-id failures) is a useful reference but the new endpoint owns its own shape (`{selections: [{...}]}`).

### Latest Tech Information

- **Django 6.0.x + django-fsm.** `subscriber.recover()` is decorated `@transition(field=status, source=STATUS_ACTIVE, target=STATUS_RECOVERED)`. `TransitionNotAllowed` raised if called from non-Active — caught by the defensive `if locked.status != STATUS_ACTIVE: break` in the `_check_payment_recoveries` atomic block.
- **DRF 3.17.x.** `@throttle_classes([_BatchSendEmailThrottle])` decorator on the `@api_view` function. Throttle key derived inside the throttle subclass's `get_cache_key`. The custom exception handler at `core/views/errors.py:25-47` produces the `RATE_LIMITED` envelope; the per-scope message map at `errors.py:6-10` already supports `password_reset`/`send_email`/`mark_resolved` — Task 1.4 adds `batch_send_email`.
- **Celery 5.x.** `task.delay(args, kwargs)` enqueues. The polling caller's `transaction.on_commit(lambda fid=failure_id: send_recovery_confirmation.delay(fid, bypass_engine_active=True))` is the load-bearing pattern for "don't enqueue until the FSM transition commits". The `fid=failure_id` default-arg capture mirrors the existing pattern in `services/recovery.py:281-289`.
- **stripe-python 8.x.** `stripe.PaymentIntent.retrieve(payment_intent_id, api_key=token)` returns a `PaymentIntent` resource; `.status` is the canonical recovery signal. Possible values: `"requires_payment_method"`, `"requires_confirmation"`, `"requires_action"`, `"processing"`, `"requires_capture"`, `"canceled"`, `"succeeded"`. v1 only acts on `"succeeded"`.
- **Next.js 16 + TanStack Query v5.** `useMutation<TData, TError, TVariables>`. `useQueryClient().invalidateQueries({queryKey: [...]})`.
- **Base UI Dialog (`@base-ui/react/dialog`).** `Dialog.Root open={...} onOpenChange={...}` controls visibility imperatively. Project's primitive at `frontend/src/components/ui/dialog.tsx` wraps `Dialog.Popup` + `Dialog.Backdrop`. ESC + outside-click both call `onOpenChange(false)`.
- **Base UI Checkbox (`@base-ui/react/checkbox`).** `<Checkbox.Root checked={...} onCheckedChange={...}>` for controlled state. Indeterminate state via `indeterminate={true}` (sets `data-state="indeterminate"` on the root). The project's primitive at `frontend/src/components/ui/checkbox.tsx` re-exports the Base UI primitive with SafeNet styling.
- **sonner 2.x.** `toast.warning("...", {duration: 8000})` for partial-failure surfaces. `toast.success`/`toast.error` reused.

### Project Structure Notes

**New files to create:**
- `backend/core/views/batch_send_email.py` — `batch_send_email` view + `_BatchSendEmailThrottle` + helpers
- `backend/core/tests/test_api/test_batch_send_email.py`
- `frontend/src/components/dashboard/BulkActionToolbar.tsx`
- `frontend/src/hooks/useBatchSendEmail.ts`
- `frontend/src/hooks/useBulkFanout.ts`
- `frontend/src/__tests__/BulkActionToolbar.test.tsx`
- `frontend/src/__tests__/useBatchSendEmail.test.ts`

**Files to modify:**
- `backend/core/urls.py` — add `/batch-send-email/` route (placement matters — before the `<int:subscriber_id>` routes)
- `backend/core/tasks/polling.py` — ungate `_check_subscription_cancellations`, add `_check_payment_recoveries`, add `RECOVERY_LOOKBACK_DAYS` constant
- `backend/core/tasks/notifications.py` — add `bypass_engine_active` kwarg to `send_recovery_confirmation`
- `backend/core/views/errors.py` — add `batch_send_email` entry to `_THROTTLED_MESSAGES`
- `backend/safenet_backend/settings/base.py` — add `batch_send_email: 5/min` and bump `mark_resolved: 60/min`
- `backend/core/tests/test_tasks/test_polling.py` — `TestV1StatusDetection` class
- `backend/core/tests/test_tasks/test_notifications.py` — `bypass_engine_active` tests for `send_recovery_confirmation`
- `frontend/src/components/dashboard/FailedPaymentsList.tsx` — selection state, leading checkbox column, header "select all", `<BulkActionToolbar>` rendering, bulk callback wiring
- `frontend/src/__tests__/FailedPaymentsList.test.tsx` — new mocks (`useBatchSendEmail`, `useBulkFanout`) + selection + bulk-action tests

**Files NOT to modify:**
- `backend/core/views/send_email.py` — per-row endpoint unchanged
- `backend/core/views/dashboard.py` — `failed_payments_list` view unchanged
- `backend/core/services/dpa.py` / `audit.py` — reused as-is
- `backend/core/services/email.py` — email-builder functions reused as-is; no new templates
- `backend/core/services/recovery.py` — quarantined v0 retry logic; do NOT touch (its `process_retry_result` calls `send_recovery_confirmation` with default kwargs which preserves v0 behavior)
- `backend/core/views/actions.py` — quarantined v0 batch-approve view; pattern reference only
- `frontend/src/types/failed_payment.ts` — types unchanged
- `frontend/src/hooks/useFailedPayments.ts` / `useSendEmail.ts` / `useMarkResolved.ts` / `useExcludeSubscriber.ts` — reused; no edits
- `frontend/src/components/review/BatchActionToolbar.tsx` — v0 quarantined component; visual reference only, NOT imported

**Files to delete:** none.

### References

- [Source: epics.md#Story 3.4 (v1):906-944] — ACs and FR coverage (FR54, FR17, FR18)
- [Source: epics.md#FR17:139 / FR18:140 / FR25:147 / FR53:183 / FR54:184] — functional-requirement traceability
- [Source: prd.md#FR17:497 / FR18:498 / FR25:509 / FR54:490] — PRD-level FR statements
- [Source: prd.md#NFR-R1:551 / NFR-R2:552] — daily polling cadence + Marc-trigger latency
- [Source: sprint-change-proposal-2026-04-29.md §2e:158] — explicit "1 new endpoint: `/batch-send-email/`"
- [Source: sprint-change-proposal-2026-04-29.md §2d:134] — quarantine map: card-update detection removed, cancellation polling stays
- [Source: sprint-change-proposal-2026-04-29.md §4.3 Edit 12:651-660] — data-flow rewrite: polling drives Active → Recovered + Active → Passive Churn for v1
- [Source: ux-design-specification.md#BatchActionToolbar:963-979] — toolbar anatomy + states + accessibility
- [Source: ux-design-specification.md#12.1:1052-1056] — single-Primary-CTA-per-bulk-bar rule
- [Source: ux-design-specification.md User Flows lines 703-712] — bulk send confirmation dialog flow
- [Source: architecture.md#Naming Patterns:398-435] — snake_case + kebab-case URLs
- [Source: architecture.md#Format Patterns:489-510] — response envelope contract
- [Source: architecture.md#Structure Patterns:439-477] — Django app organization (one route, one file)
- [Source: architecture.md#Process Patterns:570-590] — error handling by layer + TanStack Query mutations
- [Source: 3-1-v1-dpa-acceptance-gate.md] — `require_dpa_accepted` contract; tooltip precedence
- [Source: 3-2-v1-current-month-failed-payments-dashboard.md] — `FailedPaymentsList` shape, `["failed-payments"]` cache key
- [Source: 3-3-v1-per-row-send-and-manual-resolve.md] — `send_dunning_email` task, `_passes_gates(bypass_engine_active)`, `_SendEmailThrottle`/`_MarkResolvedThrottle` SimpleRateThrottle pattern, `useSendEmail` + `SendEmailError` envelope, sonner Toaster mount, dropdown-menu test mock pattern
- [Source: 4-3-final-notice-recovery-confirmation-emails.md] — `send_recovery_confirmation_email` builder + NotificationLog dedup constraint
- [Source: 4-4-opt-out-mechanism-notification-suppression.md] — `NotificationOptOut` per-(email, account) keying + case-insensitive lookup
- [Source: backend/core/tasks/polling.py:357-410] — existing `_check_subscription_cancellations` body (no body changes; Task 2.2 only ungates the call site)
- [Source: backend/core/tasks/polling.py:148-158] — current `is_engine_active` gate around cancellation/card-update calls
- [Source: backend/core/tasks/notifications.py:289-381] — current `send_recovery_confirmation` task (Task 3.2 adds bypass kwarg)
- [Source: backend/core/views/send_email.py:24-50, 53-183] — `_SendEmailThrottle` + `send_email` view (mirror for batch)
- [Source: backend/core/views/actions.py:13, 36-106] — `MAX_BATCH_SIZE` constant + `batch_approve_actions` per-id failure shape (reference only)
- [Source: backend/core/models/subscriber.py:32-60] — FSM transitions including `recover()`
- [Source: backend/core/models/notification.py:42-54] — partial unique constraint on NotificationLog
- [Source: backend/core/services/dpa.py:25-43] — `require_dpa_accepted` contract
- [Source: backend/core/services/audit.py:11-50] — `write_audit_event` helper
- [Source: backend/core/views/errors.py:6-22] — per-scope throttled-message map
- [Source: backend/safenet_backend/settings/base.py:104-110] — `DEFAULT_THROTTLE_RATES` (Task 1.4 + 11.1 edit here)
- [Source: backend/safenet_backend/celery.py:13-22] — beat schedule (no changes; daily polling already at 86_400s)
- [Source: frontend/src/components/dashboard/FailedPaymentsList.tsx:350-441] — current shape (Task 10 edits this)
- [Source: frontend/src/components/ui/checkbox.tsx] — Base UI Checkbox primitive (used in leading column)
- [Source: frontend/src/components/ui/dialog.tsx] — Dialog primitives (used in confirmation dialog)
- [Source: frontend/src/components/review/BatchActionToolbar.tsx:1-49] — v0 toolbar visual reference (DO NOT import)
- [Source: frontend/src/hooks/useSendEmail.ts:8, 27-41] — `SendableEmailType` + `SendEmailError` reuse
- [Source: frontend/src/hooks/useExcludeSubscriber.ts:12-26] / `useMarkResolved.ts:13-26` — per-row mutation hook shape (used by useBulkFanout fan-out targets)
- [Source: frontend/src/__tests__/FailedPaymentsList.test.tsx:74-108] — Radix DropdownMenu test mock pattern (reuse in `BulkActionToolbar.test.tsx`)
- [Source: frontend/src/__tests__/useSendEmail.test.ts:1-80] — hook test scaffold pattern (reuse in `useBatchSendEmail.test.ts`)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

- Initial run of `core/tests/test_api/test_batch_send_email.py` failed `test_no_account_returns_404` because `Account.user` is not the FK name (`owner` is). The test was a defensive corner-case beyond AC #1-#11; removed it (the existing per-row `send_email` view has no equivalent test either).
- ESLint flagged `react-hooks/set-state-in-effect` on the original "clear selectedIds on data identity change" `useEffect`. Replaced with the natural intersection: `selectedRows = data.filter(r => selectedIds.has(r.id))`. Preserves the same UX (rows the refetch drops are simply not selected anymore) without the cascading-render anti-pattern.
- Frontend test mocks for `@/components/ui/dropdown-menu` had to handle Base UI's `render={...}` prop in addition to the legacy `asChild` pattern: `render` receives a trigger element that we `cloneElement` with the Trigger's children injected. Without this, aria-label-bearing buttons inside the `render` element are not queryable in jsdom.
- `_check_payment_recoveries` recovery test required `TransactionTestCase` (`django.test.TestCase` subclass with `transaction=True`) so `captureOnCommitCallbacks(execute=True)` could fire the `transaction.on_commit` lambda that dispatches the recovery email. Pure pytest fixtures wrap each test in a transaction that never commits, so on_commit callbacks never fire.

### Completion Notes List

- All ACs 1–11 implemented and covered by automated tests (Task 14 manual smoke verification deferred to reviewer per the story spec).
- New backend route `POST /api/v1/subscribers/batch-send-email/` registered before the `<int:subscriber_id>/...` routes so URL resolution does not try to convert "batch-send-email" to an int.
- Throttle scope `batch_send_email` (5/min) is independent of `send_email` (10/min) — each subclass has its own cache key.
- `mark_resolved` throttle bumped from 10/min → 60/min to support bulk fan-out (≤50 rows). `mark_resolved` has no external side effect (FSM transition + audit only), so the looser cap is safe.
- Polling-driven Active → Passive Churn now runs for v1 accounts (engine_mode=None) — `_check_subscription_cancellations` ungated. Active → Recovered detection added via new `_check_payment_recoveries` helper; Mid/Pro + DPA accepted accounts also dispatch `send_recovery_confirmation.delay(failure.id, bypass_engine_active=True)`.
- `send_recovery_confirmation` task gained `bypass_engine_active: bool = False` kwarg (default preserves the v0 retry-success caller). Audit metadata gains `trigger="polling_recovery"` when bypass is True; v0 callers continue to write the original metadata shape.
- Card-update detection (`_detect_card_updates`) intentionally stays gated behind `is_engine_active` — confirmed by `test_card_update_detection_remains_gated_in_v1` in `TestCardUpdateQuarantineGuard`.
- Frontend bulk toolbar uses Base UI Dialog + DropdownMenu primitives (focus trap, ESC, return-focus handled by Base UI). `BulkActionToolbar` is rendered always; it returns null when `selectedRows.length === 0` so it never mounts on Free-tier (their `effectiveSelectedIds` is forced to empty).
- `useBulkFanout` issues parallel `Promise.allSettled` per-row POSTs and invalidates `["failed-payments"]` + `["dashboard","summary"]` once after the entire fan-out settles — never per-mutation.
- Backend regression: 646/648 tests green excluding `_bmad-output` story file (`test_attention_items_isolated_by_tenant` and `test_missed_cycle_alert` are pre-existing flakiness on `main`). Frontend regression: all 56 of my new+modified tests green; pre-existing failures in `BatchActionToolbar.test.tsx`/`NavBar.test.tsx`/`ProfileComplete.test.tsx`/`ReviewQueuePage.test.tsx` confirmed on clean `main`.

### File List

**New files:**
- `backend/core/views/batch_send_email.py`
- `backend/core/tests/test_api/test_batch_send_email.py`
- `frontend/src/components/dashboard/BulkActionToolbar.tsx`
- `frontend/src/hooks/useBatchSendEmail.ts`
- `frontend/src/hooks/useBulkFanout.ts`
- `frontend/src/__tests__/BulkActionToolbar.test.tsx`
- `frontend/src/__tests__/useBatchSendEmail.test.ts`

**Modified files:**
- `backend/core/urls.py` — added `/batch-send-email/` route + import.
- `backend/core/tasks/polling.py` — ungated `_check_subscription_cancellations`; added `_check_payment_recoveries` helper + `RECOVERY_LOOKBACK_DAYS` constant; wired the new helper into `poll_account_failures`.
- `backend/core/tasks/notifications.py` — `send_recovery_confirmation` gained `bypass_engine_active` kwarg + conditional `trigger="polling_recovery"` audit metadata.
- `backend/core/views/errors.py` — added `batch_send_email` entry to `_THROTTLED_MESSAGES`.
- `backend/safenet_backend/settings/base.py` — added `batch_send_email: 5/min`; bumped `mark_resolved: 10/min → 60/min`.
- `backend/core/tests/test_tasks/test_polling.py` — added `TestV1StatusDetection`, `TestPaymentRecoveryHelper`, `TestCardUpdateQuarantineGuard` classes (12 new tests).
- `backend/core/tests/test_tasks/test_notifications.py` — added 3 bypass tests under `TestSendRecoveryConfirmation`.
- `frontend/src/components/dashboard/FailedPaymentsList.tsx` — selection state, leading checkbox column with select-all header, `<BulkActionToolbar>` wiring, batch + bulk-fanout callbacks, free-tier guard.
- `frontend/src/__tests__/FailedPaymentsList.test.tsx` — new mocks (`useBatchSendEmail`, `useBulkFanout`, `dialog`, render-prop-aware DropdownMenuTrigger) + 9 new tests covering selection, bulk dispatch, toast outcomes.
- `_bmad-output/sprint-status.yaml` — story status `ready-for-dev → in-progress → review`.

### Change Log

- 2026-04-30 — Story 3.4 (v1) implementation: backend `/batch-send-email/` view + 5/min throttle; polling-driven Active → Recovered (`_check_payment_recoveries`) and Active → Passive Churn (cancellation helper ungated for v1); `send_recovery_confirmation` gained `bypass_engine_active` kwarg; frontend `BulkActionToolbar` + `useBatchSendEmail` + `useBulkFanout` + leading checkbox column on `FailedPaymentsList`; `mark_resolved` throttle bumped 10/min → 60/min. ACs 1–11 covered by 24 new backend tests and 29 new frontend tests (Task 14 manual smoke deferred to reviewer).

