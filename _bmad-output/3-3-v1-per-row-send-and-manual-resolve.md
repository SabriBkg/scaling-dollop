# Story 3.3 (v1): Per-Row Send & Manual Resolve

Status: done

> **v1 scope (post-2026-04-29 simplification).** Replaces the quarantined `3-3-card-update-detection-immediate-retry.md` (v0). v1 has no automated retries — clients trigger every email by hand from the failed-payments dashboard. See `_bmad-output/sprint-change-proposal-2026-04-29.md`.

> **Inheriting infrastructure already on `main`** (do NOT recreate):
> - `Account.dpa_accepted` property + `Account.dpa_version` field — `backend/core/models/account.py:43-89`
> - `require_dpa_accepted(account)` gate helper (returns 403 `DPA_REQUIRED` envelope) — `backend/core/services/dpa.py:25-43`
> - `Subscriber` FSM with `recover()` (active → recovered), `mark_passive_churn()`, `mark_fraud_flagged()` — `backend/core/models/subscriber.py:16-58`. The `post_transition` signal at `subscriber.py:87-99` writes a `status_<target>` audit on every transition.
> - `SubscriberFailure` model with `payment_intent_id`, `decline_code`, `amount_cents`, `failure_created_at` — `backend/core/models/subscriber.py:60-84`
> - `NotificationLog` with partial unique constraint on `(failure, email_type) WHERE status="sent"` — `backend/core/models/notification.py:18-52`
> - `NotificationOptOut` model + opt-out check inside `_passes_gates` — `backend/core/models/notification.py:55-67`, `backend/core/tasks/notifications.py:64-69`
> - Celery tasks `send_failure_notification`, `send_final_notice`, `send_recovery_confirmation` — `backend/core/tasks/notifications.py:97-373`
> - Email-builder service functions `send_notification_email`, `send_final_notice_email`, `send_recovery_confirmation_email` — `backend/core/services/email.py:374-554`
> - `_passes_gates` 6-gate sequence (engine_active, no_email, excluded, opt_out, duplicate, final_notice→active) — `backend/core/tasks/notifications.py:31-94`. **Story 3.3 makes Gate 1 (engine_active) skippable** for client-triggered sends — see Task 2.
> - `_log_suppression`, `_record_failure` helpers — `backend/core/tasks/notifications.py:376-461`
> - `write_audit_event()` helper — `backend/core/services/audit.py:11-50`
> - `Subscriber.objects.for_account(account.id)` tenant-scope manager — `backend/core/models/base.py:13-15`
> - `POST /api/v1/subscribers/{id}/exclude/` view (`exclude_subscriber`) writing `subscriber_excluded` audit — `backend/core/views/actions.py:109-148`
> - `failed_payments_list` view + `FailedPaymentRowSerializer` (returns `recommended_email_type` always `null` until Story 3.5 v1) — `backend/core/views/dashboard.py:210-287`, `backend/core/serializers/dashboard.py:32-45`
> - DRF `ScopedRateThrottle` wired as default; `DEFAULT_THROTTLE_RATES` config in `backend/safenet_backend/settings/base.py:103-108`. Existing scopes: `auth`, `profile`, `password_reset`. Custom exception handler at `backend/core/views/errors.py:9-31` already maps `Throttled` → `RATE_LIMITED` envelope and surfaces `wait` seconds (override below).
> - Frontend `FailedPaymentsList` component with action-button column (currently 3 disabled placeholder Ghost buttons: Send / Mark resolved / Exclude) + tier/DPA/placeholder tooltip precedence — `frontend/src/components/dashboard/FailedPaymentsList.tsx:148-318`. **Story 3.3 lifts the placeholder gate** (`actionsDisabled = true`) and wires real mutations.
> - Frontend `useFailedPayments` TanStack Query hook with key `["failed-payments", sort, dir]`, `staleTime: 5 * 60 * 1000` — `frontend/src/hooks/useFailedPayments.ts:12-28`
> - Frontend `useDpaGate` hook returning `{dpaAccepted, loading, sendDisabled, tooltip, activatePath}` — `frontend/src/hooks/useDpaGate.ts:13-30`
> - Frontend `useAccount` with `tier`, `dpa_accepted`, `dpa_version` — `frontend/src/hooks/useAccount.ts`
> - Frontend `useExcludeSubscriber` mutation hook (POSTs to `/subscribers/{id}/exclude/`, invalidates `["actions","pending"]` + `["dashboard","summary"]`) — `frontend/src/hooks/useExcludeSubscriber.ts:11-26`. **Story 3.3 extends its `onSuccess` to also invalidate `["failed-payments"]`** — see Task 8.4.
> - Frontend types `FailedPayment`, `RecommendedEmailType` (`update_payment | retry_reminder | final_notice | null`) — `frontend/src/types/failed_payment.ts:1-25`
> - shadcn primitives in `frontend/src/components/ui/`: `button.tsx`, `dropdown-menu.tsx` (used by `UserMenu.tsx`), `dialog.tsx`, `sonner.tsx` (Toaster wrapper). `lucide-react` icons available.
> - `sonner` toast API: `toast.success(...)`, `toast.error(...)`, `toast.warning(...)`. Existing call sites: `frontend/src/app/(dashboard)/review-queue/page.tsx:42-103`, `frontend/src/components/settings/ToneSelector.tsx:58-62`.

## Story

As a Mid-tier founder,
I want to trigger a recommended (or chosen) dunning email per failed-payment row, and to manually mark failures as resolved or excluded,
So that I act on each case without leaving the dashboard.

## Acceptance Criteria

1. **Given** a row with `subscriber_status="active"` and a non-null `recommended_email_type` **When** the client clicks "Send recommended" **Then** the frontend POSTs to `/api/v1/subscribers/{subscriber_id}/send-email/` with body `{"email_type": <recommended>, "failure_id": <row.id>}` **And** the view runs (in this exact order): DPA gate → tier gate (Free=403) → tenant scope → opt-out check → exclusion check → enqueue Celery task **And** an audit row is written with `actor="client"`, `action="email_sent"`, `metadata={"email_type": <type>, "trigger": "client_manual", "failure_id": <id>}` (FR53) **And** the Celery task delivers via the existing Resend integration **And** a `NotificationLog` row is created with the requested `email_type` and `status="sent"` **And** the response is `202 Accepted` with body `{"data": {"queued": true, "email_type": <type>, "failure_id": <id>}}`.

2. **Given** a row with `subscriber_status="active"` **When** the client opens the per-row "Send specific email" dropdown **Then** the dropdown lists exactly three options: "Update payment" (`update_payment`), "Retry reminder" (`retry_reminder`), "Final notice" (`final_notice`) **And** selecting any option sends that `email_type` via the same `/send-email/` endpoint **And** the audit row's `metadata.email_type` matches the chosen value **And** the chosen-type send is subject to the same DPA / tier / opt-out / exclusion / rate-limit gates as AC1.

3. **Given** a row with any `subscriber_status` (active, recovered, passive_churn, or fraud_flagged) **When** the client clicks "Mark resolved" **Then** the frontend POSTs to `/api/v1/subscribers/{subscriber_id}/mark-resolved/` (no body) **And** the subscriber FSM transitions to `recovered` via the new `mark_resolved_manually()` transition **And** an audit row is written with `actor="client"`, `action="manual_resolved"`, `metadata={"trigger": "client_manual", "from": <prior_status>}` (FR55) **And** the response is `200 OK` with body `{"data": {"resolved": true, "subscriber_id": <id>, "from_status": <prior>, "to_status": "recovered"}}` **And** the failed-payments query cache is invalidated so the row re-renders with a `recovered` status badge **And** invoking `mark_resolved_manually()` on a subscriber whose status is already `recovered` returns `400 INVALID_TRANSITION` (no audit, no FSM mutation).

4. **Given** a row **When** the client clicks "Exclude from future recommendations" **Then** the frontend POSTs to the existing `/api/v1/subscribers/{subscriber_id}/exclude/` endpoint (already on main) **And** `subscriber.excluded_from_automation` becomes `true` **And** the existing `subscriber_excluded` audit fires (no change to the backend audit shape) **And** the failed-payments query cache is invalidated so the row's recommendation chip flips to `—` once Story 3.5 lands.

5. **Given** any send attempt for a subscriber whose `(subscriber.email, account)` tuple has a `NotificationOptOut` row **When** the `/send-email/` endpoint is called **Then** the view returns `422 OPT_OUT` with envelope `{"error": {"code": "OPT_OUT", "message": "Subscriber has opted out of notifications.", "field": null}}` **And** no Celery task is enqueued **And** no Resend call is made **And** an audit row is written with `actor="client"`, `action="email_sent_blocked"`, `outcome="skipped"`, `metadata={"reason": "opt_out", "email_type": <type>, "failure_id": <id>}` (FR26, FR27).

6. **Given** an account that has already POSTed 10 successful (non-error) requests to `/send-email/` within the last 60 seconds **When** the client triggers an 11th send within the window **Then** the API responds `429 Too Many Requests` with envelope `{"error": {"code": "RATE_LIMITED", "message": "Too many email send requests. Try again later.", "field": null}}` and the standard DRF `Retry-After` header **And** the frontend surfaces a non-blocking `toast.error("Rate limit reached. Try again in <N>s.", { duration: 6000 })` **And** the row's "Send recommended" / dropdown items remain interactive (the rate limit is per-account, not per-row).

7. **Given** a Free-tier account **When** any of `/send-email/` or `/mark-resolved/` is called **Then** the response is `403 FORBIDDEN` with envelope `{"error": {"code": "TIER_REQUIRED", "message": "Upgrade to Mid or Pro to enable email actions.", "field": null}}` (Mark resolved is also paid because it is a Mid-tier capability per the PRD; Free remains view-only) **And** the frontend never sends those requests for Free-tier users — buttons stay disabled with the tier tooltip from Story 3.2 v1's precedence chain.

## Tasks / Subtasks

### Backend

- [x] **Task 1: Extend `EMAIL_TYPE_CHOICES` to cover the 3 client-facing types** (AC: #1, #2)
  - [x] 1.1 Edit `backend/core/models/notification.py:5-9`. Add two entries to `EMAIL_TYPE_CHOICES`:
    ```python
    EMAIL_TYPE_CHOICES = [
        ("failure_notice", "Failure Notice"),
        ("update_payment", "Update Payment"),    # Story 3.3 v1 — client-triggered "update your card"
        ("retry_reminder", "Retry Reminder"),    # Story 3.3 v1 — client-triggered nudge
        ("final_notice", "Final Notice"),
        ("recovery_confirmation", "Recovery Confirmation"),
    ]
    ```
    Keep `failure_notice` (still emitted by quarantined v0 polling code on `main`) and `recovery_confirmation` (Story 4.3) untouched. The `max_length=30` on `email_type` already accommodates `update_payment` (14) and `retry_reminder` (14).
  - [x] 1.2 Create migration `backend/core/migrations/0016_extend_notification_email_type_choices.py` (latest on `main` is `0015_add_dpa_version_to_account.py` per Story 3.1 v1; verify with `ls backend/core/migrations/ | tail -5` and bump if a sibling branch already took 0016). The migration is `AlterField` on `NotificationLog.email_type` — choices-only change, NO data migration. Reference shape in `backend/core/migrations/0006_add_dpa_engine_mode_to_account.py`.
  - [x] 1.3 Run `cd backend && poetry run python manage.py makemigrations --dry-run` to confirm Django wants exactly the choices change. If it surfaces unrelated changes, abort and ask Sabri before continuing (per the established 3-1-v1 convention).

- [x] **Task 2: Make `_passes_gates` skip Gate 1 for client-manual sends** (AC: #1, #2)
  - [x] 2.1 Edit `backend/core/tasks/notifications.py:31-94`. Add a `bypass_engine_active: bool = False` keyword-only parameter to `_passes_gates`:
    ```python
    def _passes_gates(
        subscriber, failure, account,
        *,
        email_type: str,
        log_label: str,
        bypass_engine_active: bool = False,
    ) -> bool:
    ```
    Inside the function, wrap the existing Gate 1 block so it is skipped when `bypass_engine_active=True`:
    ```python
    # Gate 1: Engine must be active (Mid/Pro + DPA + engine mode).
    # v1 client-manual sends bypass this gate — DPA is enforced at the view
    # boundary via require_dpa_accepted(); engine_mode is moot in v1.
    if not bypass_engine_active and not is_engine_active(account):
        _log_suppression(subscriber, failure, account, reason="engine_not_active", email_type=email_type)
        return False
    ```
    Do NOT change Gates 2–6 — they all remain (no_email, excluded, opt_out, duplicate, final_notice→active). The existing 3 callers (`send_failure_notification`, `send_final_notice`, `send_recovery_confirmation`) DO NOT pass `bypass_engine_active`, so default `False` preserves v0 behavior. ONLY the new `send_dunning_email` task (Task 3) passes `bypass_engine_active=True`.

- [x] **Task 3: New Celery task `send_dunning_email` (router for client-manual sends)** (AC: #1, #2)
  - [x] 3.1 Add to `backend/core/tasks/notifications.py` directly under `send_recovery_confirmation` (so the file flows: existing 3 tasks → new client-manual task → helpers). Task signature:
    ```python
    CLIENT_MANUAL_EMAIL_TYPES = ("update_payment", "retry_reminder", "final_notice")


    @app.task(bind=True, max_retries=3, default_retry_delay=60)
    def send_dunning_email(self, failure_id: int, email_type: str):
        """Send a client-triggered dunning email (Story 3.3 v1).

        Routes to the correct email-builder by email_type and persists a
        NotificationLog row keyed on (failure, email_type). Bypasses
        Gate 1 (engine_active) — DPA is enforced at the view boundary.
        """
        logger.info("[send_dunning_email] START failure_id=%s email_type=%s", failure_id, email_type)

        if email_type not in CLIENT_MANUAL_EMAIL_TYPES:
            logger.error("[send_dunning_email] Unknown email_type=%s — refusing", email_type)
            return

        try:
            failure = (
                SubscriberFailure.objects
                .select_related("subscriber", "account", "account__stripe_connection")
                .get(id=failure_id)
            )
        except SubscriberFailure.DoesNotExist:
            logger.error("[send_dunning_email] Failure %s not found", failure_id)
            return

        subscriber = failure.subscriber
        account = failure.account

        if not _passes_gates(
            subscriber, failure, account,
            email_type=email_type, log_label="send_dunning_email",
            bypass_engine_active=True,
        ):
            return

        # Route by email_type — update_payment + retry_reminder share the
        # failure-notice template (decline-code-aware CTA copy); final_notice
        # has its own template per Story 4.3.
        try:
            if email_type == "final_notice":
                msg_id = send_final_notice_email(subscriber, failure, account)
            else:
                # update_payment | retry_reminder
                msg_id = send_notification_email(subscriber, failure, account)

            try:
                NotificationLog.objects.create(
                    account=account,
                    subscriber=subscriber,
                    failure=failure,
                    email_type=email_type,
                    resend_message_id=msg_id,
                    status="sent",
                )
            except IntegrityError:
                logger.info(
                    "[send_dunning_email] DUPLICATE_RACE failure_id=%s email_type=%s msg_id=%s",
                    failure_id, email_type, msg_id,
                )
                _log_suppression(
                    subscriber, failure, account,
                    reason="duplicate_race", email_type=email_type,
                    extra_metadata={"resend_message_id": msg_id},
                )
                return

            write_audit_event(
                subscriber=str(subscriber.id),
                actor="engine",
                action="notification_sent",
                outcome="success",
                metadata={
                    "email_type": email_type,
                    "decline_code": failure.decline_code,
                    "resend_message_id": msg_id,
                    "trigger": "client_manual",
                },
                account=account,
            )
            logger.info("[send_dunning_email] COMPLETE failure_id=%s msg_id=%s", failure_id, msg_id)

        except SkipNotification as exc:
            logger.info(
                "[send_dunning_email] SKIPPED failure_id=%s reason=%s",
                failure_id, exc,
            )
            _log_suppression(subscriber, failure, account, reason="skip_permanent", email_type=email_type)
            return

        except EmailConfigurationError as exc:
            logger.error("[send_dunning_email] CONFIG ERROR failure_id=%s error=%s", failure_id, exc)
            _record_failure(subscriber, failure, account, exc, email_type=email_type, task_name="send_dunning_email")
            return

        except Exception as exc:
            logger.error("[send_dunning_email] FAILED failure_id=%s error=%s", failure_id, exc)
            if self.request.retries >= self.max_retries:
                _record_failure(subscriber, failure, account, exc, email_type=email_type, task_name="send_dunning_email")
                return
            raise self.retry(exc=exc)
    ```
    Mirror the structure of `send_failure_notification` exactly so the retry/DLL/audit machinery stays uniform. The `metadata.trigger` key is the new signal that distinguishes engine-driven (`client_manual` absent) from client-triggered (`client_manual` present) `notification_sent` rows.
  - [x] 3.2 The `send_recovery_confirmation` task is NOT consumed by Story 3.3 (mark-resolved is a state transition, not an email). Out of scope for this story.

- [x] **Task 4: Add `Subscriber.mark_resolved_manually()` FSM transition** (AC: #3)
  - [x] 4.1 Edit `backend/core/models/subscriber.py:32-45`. Add a fourth `@transition`-decorated method directly under `mark_fraud_flagged()`:
    ```python
    @transition(
        field=status,
        source=[STATUS_ACTIVE, STATUS_PASSIVE_CHURN, STATUS_FRAUD_FLAGGED],
        target=STATUS_RECOVERED,
    )
    def mark_resolved_manually(self):
        """Story 3.3 v1 — client manually marks a failure as resolved.

        Allowed from any non-recovered state. The post_transition signal
        emits a `status_recovered` audit row; the view layer ALSO writes
        a `manual_resolved` audit with the prior status so the trail
        captures intent (engine vs client-manual).
        """
        pass
    ```
    Source list deliberately excludes `STATUS_RECOVERED` so calling on an already-recovered subscriber raises `TransitionNotAllowed` — caught at the view boundary as `400 INVALID_TRANSITION` per AC3.
  - [x] 4.2 The existing `post_transition` signal (`subscriber.py:87-99`) will fire and write a `status_recovered` audit. Do NOT modify the signal — the view layer adds a complementary `manual_resolved` audit (Task 6.4) so the auditor sees both verbs.

- [x] **Task 5: New view `send_email`** (AC: #1, #2, #5, #6, #7)
  - [x] 5.1 Add a new file `backend/core/views/send_email.py` (do not bloat `actions.py` — it already houses the v0 PendingAction views; the new send view belongs in its own module per `architecture.md#Structure Patterns:439-477` "one route, one file" preference for v1 endpoints). Imports:
    ```python
    from rest_framework import status
    from rest_framework.decorators import api_view, permission_classes, throttle_classes
    from rest_framework.permissions import IsAuthenticated
    from rest_framework.response import Response
    from rest_framework.throttling import ScopedRateThrottle

    from core.models.account import TIER_FREE
    from core.models.notification import NotificationOptOut
    from core.models.subscriber import Subscriber, SubscriberFailure
    from core.services.audit import write_audit_event
    from core.services.dpa import require_dpa_accepted
    from core.tasks.notifications import CLIENT_MANUAL_EMAIL_TYPES, send_dunning_email
    ```
  - [x] 5.2 Define a scoped throttle class (10/min per user):
    ```python
    class _SendEmailThrottle(ScopedRateThrottle):
        scope = "send_email"
    ```
  - [x] 5.3 Implement `send_email(request, subscriber_id)`:
    ```python
    @api_view(["POST"])
    @permission_classes([IsAuthenticated])
    @throttle_classes([_SendEmailThrottle])
    def send_email(request, subscriber_id: int):
        """POST /api/v1/subscribers/{id}/send-email/ — queue a client-triggered dunning email."""
        try:
            account = request.user.account
        except request.user.__class__.account.RelatedObjectDoesNotExist:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "No account found.", "field": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 1. DPA gate — must be FIRST (per dpa.py docstring & 3-1-v1 contract)
        dpa_response = require_dpa_accepted(account)
        if dpa_response is not None:
            return dpa_response

        # 2. Tier gate — Free is view-only
        if account.tier == TIER_FREE:
            return Response(
                {"error": {
                    "code": "TIER_REQUIRED",
                    "message": "Upgrade to Mid or Pro to enable email actions.",
                    "field": None,
                }},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3. Validate body
        email_type = request.data.get("email_type")
        failure_id = request.data.get("failure_id")
        if email_type not in CLIENT_MANUAL_EMAIL_TYPES:
            return Response(
                {"error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"email_type must be one of {list(CLIENT_MANUAL_EMAIL_TYPES)}.",
                    "field": "email_type",
                }},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(failure_id, int):
            return Response(
                {"error": {
                    "code": "VALIDATION_ERROR",
                    "message": "failure_id must be an integer.",
                    "field": "failure_id",
                }},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Tenant-scoped lookups
        try:
            subscriber = Subscriber.objects.for_account(account.id).get(id=subscriber_id)
        except Subscriber.DoesNotExist:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Subscriber not found.", "field": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            failure = SubscriberFailure.objects.for_account(account.id).get(
                id=failure_id, subscriber_id=subscriber.id,
            )
        except SubscriberFailure.DoesNotExist:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Failure not found for this subscriber.", "field": "failure_id"}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 5. Opt-out check at view boundary (so client gets a clear error,
        #    not a silent suppression in the task)
        sub_email = (subscriber.email or "").strip().lower()
        if sub_email and NotificationOptOut.objects.for_account(account.id).filter(
            subscriber_email__iexact=sub_email,
        ).exists():
            write_audit_event(
                subscriber=str(subscriber.id),
                actor="client",
                action="email_sent_blocked",
                outcome="skipped",
                metadata={"reason": "opt_out", "email_type": email_type, "failure_id": failure_id},
                account=account,
            )
            return Response(
                {"error": {"code": "OPT_OUT", "message": "Subscriber has opted out of notifications.", "field": None}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 6. Exclusion check
        if subscriber.excluded_from_automation:
            write_audit_event(
                subscriber=str(subscriber.id),
                actor="client",
                action="email_sent_blocked",
                outcome="skipped",
                metadata={"reason": "excluded", "email_type": email_type, "failure_id": failure_id},
                account=account,
            )
            return Response(
                {"error": {"code": "EXCLUDED", "message": "Subscriber is excluded from automation.", "field": None}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 7. Enqueue task + write client-trigger audit
        send_dunning_email.delay(failure_id, email_type)
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="client",
            action="email_sent",
            outcome="success",
            metadata={"email_type": email_type, "trigger": "client_manual", "failure_id": failure_id},
            account=account,
        )
        return Response(
            {"data": {"queued": True, "email_type": email_type, "failure_id": failure_id}},
            status=status.HTTP_202_ACCEPTED,
        )
    ```
    Order of gates is **load-bearing**: DPA → tier → body validation → tenant lookup → opt-out → exclusion → enqueue. The 3-1-v1 review (Patch line 215) flagged that putting validation before DPA leaks `VALIDATION_ERROR` to unsigned accounts — keep DPA first.
  - [x] 5.4 The `email_sent` audit is written BEFORE the Celery task delivers (it records *intent*, per AC1's `trigger: "client_manual"` requirement). The Celery task ALSO writes a `notification_sent` audit (actor=engine) on successful delivery — both rows are intentional and complementary; tests assert both.

- [x] **Task 6: New view `mark_resolved`** (AC: #3, #7)
  - [x] 6.1 Add `mark_resolved(request, subscriber_id)` to the same `backend/core/views/send_email.py` (or split into `backend/core/views/subscriber_actions.py` if you prefer; since both are subscriber-scoped client actions and there are exactly 2 such views in this story, single file is fine — the `actions.py` name is taken by the v0 batch view and shouldn't be reused).
  - [x] 6.2 Imports needed:
    ```python
    from django_fsm import TransitionNotAllowed
    ```
  - [x] 6.3 Implementation:
    ```python
    @api_view(["POST"])
    @permission_classes([IsAuthenticated])
    def mark_resolved(request, subscriber_id: int):
        """POST /api/v1/subscribers/{id}/mark-resolved/ — manually mark as Recovered."""
        try:
            account = request.user.account
        except request.user.__class__.account.RelatedObjectDoesNotExist:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "No account found.", "field": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # DPA + tier gates (parity with send_email — Mark resolved is also paid)
        dpa_response = require_dpa_accepted(account)
        if dpa_response is not None:
            return dpa_response
        if account.tier == TIER_FREE:
            return Response(
                {"error": {
                    "code": "TIER_REQUIRED",
                    "message": "Upgrade to Mid or Pro to enable email actions.",
                    "field": None,
                }},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            subscriber = Subscriber.objects.for_account(account.id).get(id=subscriber_id)
        except Subscriber.DoesNotExist:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Subscriber not found.", "field": None}},
                status=status.HTTP_404_NOT_FOUND,
            )

        prior_status = subscriber.status
        try:
            subscriber.mark_resolved_manually()
        except TransitionNotAllowed:
            return Response(
                {"error": {
                    "code": "INVALID_TRANSITION",
                    "message": f"Cannot mark resolved from status '{prior_status}'.",
                    "field": None,
                }},
                status=status.HTTP_400_BAD_REQUEST,
            )
        subscriber.save(update_fields=["status"])

        write_audit_event(
            subscriber=str(subscriber.id),
            actor="client",
            action="manual_resolved",
            outcome="success",
            metadata={"trigger": "client_manual", "from": prior_status},
            account=account,
        )
        return Response(
            {"data": {
                "resolved": True,
                "subscriber_id": subscriber.id,
                "from_status": prior_status,
                "to_status": "recovered",
            }},
            status=status.HTTP_200_OK,
        )
    ```
  - [x] 6.4 The `post_transition` signal in `subscriber.py:87-99` already writes a `status_recovered` audit on the FSM mutation — that row coexists with the view-written `manual_resolved` row. Tests assert both exist.

- [x] **Task 7: Wire URLs + throttle config** (AC: #1, #3, #6)
  - [x] 7.1 Edit `backend/core/urls.py:1-29`:
    - Add import: `from core.views.send_email import send_email, mark_resolved`
    - Add 2 routes directly under the existing `exclude_subscriber` route at line 24:
      ```python
      path("v1/subscribers/<int:subscriber_id>/send-email/", send_email, name="subscriber_send_email"),
      path("v1/subscribers/<int:subscriber_id>/mark-resolved/", mark_resolved, name="subscriber_mark_resolved"),
      ```
      Kebab-case multi-word per `architecture.md#Naming Patterns:410`.
  - [x] 7.2 Edit `backend/safenet_backend/settings/base.py:104-108`. Add the `send_email` scope to `DEFAULT_THROTTLE_RATES`:
    ```python
    "DEFAULT_THROTTLE_RATES": {
        "auth": "5/min",
        "profile": "3/min",
        "password_reset": "3/hour",
        "send_email": "10/min",  # Story 3.3 v1 — per-user (effectively per-account) cap on client-manual sends
    },
    ```
  - [x] 7.3 Update the throttled-message map in `backend/core/views/errors.py`. The existing `_THROTTLED_MESSAGE` constant is hardcoded to the password-reset wording, which is wrong for `send_email`. **Before refactoring**, run `grep -rn "_THROTTLED_MESSAGE" backend/` to find any tests or callers that import the symbol directly — update them to the new `_THROTTLED_MESSAGES` map name. Refactor to a per-scope map:
    ```python
    _THROTTLED_MESSAGES = {
        "password_reset": "Too many password reset requests. Try again later.",
        "send_email": "Too many email send requests. Try again later.",
    }
    _THROTTLED_DEFAULT_MESSAGE = "Too many requests. Try again later."

    def _throttled_message(exc, context) -> str:
        view = context.get("view") if context else None
        scope = None
        if view is not None:
            for cls in getattr(view, "throttle_classes", []) or []:
                scope = getattr(cls, "scope", None)
                if scope:
                    break
        return _THROTTLED_MESSAGES.get(scope, _THROTTLED_DEFAULT_MESSAGE)
    ```
    Then in `custom_exception_handler`:
    ```python
    if isinstance(exc, Throttled):
        message = _throttled_message(exc, context)
    else:
        message = _get_error_message(response.data)
    ```
    Existing `auth` scope (`backend/core/views/auth.py:35`) currently falls back to DRF's default message — that's pre-existing and out of scope for this story; the map above only adds the `send_email` entry while preserving the existing `password_reset` mapping. The `Retry-After` header is already set automatically by DRF — no manual handling needed; the frontend reads it via the axios `error.response.headers["retry-after"]` field.

- [x] **Task 8: Backend tests — `send_email` endpoint** (AC: #1, #2, #5, #6, #7)
  - [x] 8.1 Create `backend/core/tests/test_api/test_send_email.py`. Use `pytest.mark.django_db`, `auth_client`, `account`, `user` fixtures from `backend/core/tests/conftest.py:1-38`. For tenant-isolation tests, add `second_user` / `second_account` / `second_auth_client` inside the test file (mirror `backend/core/tests/test_api/test_subscribers.py:14-33`). For Mid-tier + DPA fixture, set in test setup:
    ```python
    @pytest.fixture
    def mid_account_with_dpa(account):
        from django.utils import timezone
        from core.services.dpa import CURRENT_DPA_VERSION
        account.tier = "mid"
        account.dpa_accepted_at = timezone.now()
        account.dpa_version = CURRENT_DPA_VERSION
        account.save(update_fields=["tier", "dpa_accepted_at", "dpa_version"])
        return account
    ```
  - [x] 8.2 Tests to write (use `URL = "/api/v1/subscribers/{id}/send-email/"` with `.format(id=...)`):
    - `test_requires_authentication` — unauthenticated POST → 401.
    - `test_dpa_required_returns_403` — Mid-tier, no DPA → 403, code `"DPA_REQUIRED"`.
    - `test_free_tier_returns_403` — DPA accepted but tier=free → 403, code `"TIER_REQUIRED"`. Confirms DPA gate runs first by also asserting that an unsigned-AND-free account returns `DPA_REQUIRED` (not `TIER_REQUIRED`).
    - `test_invalid_email_type_returns_400` — use `mid_account_with_dpa` fixture (DPA gate runs FIRST; without it, the response is 403 `DPA_REQUIRED`, not 400). Body `{"email_type": "banana", "failure_id": 1}` → 400, code `"VALIDATION_ERROR"`, field `"email_type"`.
    - `test_missing_failure_id_returns_400` — body `{"email_type": "update_payment"}` → 400, field `"failure_id"`.
    - `test_subscriber_not_found_returns_404` — non-existent subscriber_id → 404.
    - `test_failure_not_found_returns_404` — valid subscriber_id but failure_id belongs to a different subscriber → 404, field `"failure_id"`.
    - `test_opt_out_returns_422_no_task_enqueued` — pre-create `NotificationOptOut(subscriber_email=sub.email, account=account)`. Patch `core.tasks.notifications.send_dunning_email.delay` and assert `not_called`. Assert response 422, code `"OPT_OUT"`. Assert audit row created with action=`"email_sent_blocked"`, metadata.reason=`"opt_out"`.
    - `test_excluded_returns_422_no_task_enqueued` — `subscriber.excluded_from_automation = True`. Same assertions with reason=`"excluded"`.
    - `test_happy_path_queues_task_and_writes_audit` — Mid+DPA+active subscriber+failure. Patch `send_dunning_email.delay`. POST with `{"email_type": "update_payment", "failure_id": failure.id}`. Assert response 202, body `{"data": {"queued": true, "email_type": "update_payment", "failure_id": ...}}`. Assert `delay` called once with `(failure.id, "update_payment")`. Assert audit row exists with actor=`"client"`, action=`"email_sent"`, metadata={`email_type`,`trigger:"client_manual"`,`failure_id`}.
    - `test_happy_path_for_each_email_type` — parametrize over `["update_payment", "retry_reminder", "final_notice"]`. Assert each gets queued.
    - `test_tenant_isolation` — second_account creates its own subscriber+failure; first_user POSTs to second_account's subscriber_id → 404 (not 403; tenant scoping treats other-tenant rows as non-existent).
    - `test_rate_limit_429_after_10_requests` — POST 10 times with valid body. Mock `send_dunning_email.delay` so it doesn't actually run. Assert all 10 return 202. The 11th POST returns 429 with code `"RATE_LIMITED"`. Use `from django.core.cache import cache; cache.clear()` in test setup to reset throttle state. Assert `Retry-After` header is present and is a positive integer string.
    - `test_engine_active_gate_bypassed` — set `account.engine_mode = None` (it's None by default in v1). Assert the send still queues (Gate 1 is bypassed for client-manual).
  - [x] 8.3 Run `cd backend && poetry run pytest core/tests/test_api/test_send_email.py -v` — all green.

- [x] **Task 9: Backend tests — `mark_resolved` endpoint + FSM** (AC: #3, #7)
  - [x] 9.1 Create `backend/core/tests/test_api/test_mark_resolved.py`. Same fixture pattern as Task 8.
  - [x] 9.2 Tests:
    - `test_requires_authentication` — 401.
    - `test_dpa_required_returns_403` — 403 `DPA_REQUIRED`.
    - `test_free_tier_returns_403` — 403 `TIER_REQUIRED`.
    - `test_subscriber_not_found_returns_404` — non-existent subscriber.
    - `test_resolves_active_subscriber` — Mid+DPA, status=active. POST → 200 with `{"data": {"resolved": true, "subscriber_id": ..., "from_status": "active", "to_status": "recovered"}}`. Refresh from DB; assert `subscriber.status == "recovered"`. Assert TWO audit rows exist for this subscriber: one with action=`"status_recovered"` (from FSM signal, actor=engine) and one with action=`"manual_resolved"` (from view, actor=client, metadata.from=`"active"`, metadata.trigger=`"client_manual"`).
    - `test_resolves_passive_churn_subscriber` — set status=`passive_churn` directly (bypass FSM via `Subscriber.objects.filter(...).update(status="passive_churn")` to skip the `mark_passive_churn` source check; we need to start from passive_churn to test recovery from there). POST → 200, audit metadata.from=`"passive_churn"`.
    - `test_resolves_fraud_flagged_subscriber` — same as above with status=`fraud_flagged`.
    - `test_already_recovered_returns_400` — status=`recovered`, POST → 400 with code `"INVALID_TRANSITION"`. Assert NO new audit row created (subscriber audit count unchanged after the call).
    - `test_tenant_isolation` — second_account's subscriber → 404.
  - [x] 9.3 Add a unit test `backend/core/tests/test_models/test_subscriber_fsm.py::test_mark_resolved_manually_from_each_source` (create the file if missing — there's no existing FSM test module per `backend/core/tests/test_models/`). Test the FSM transition in isolation: from active → recovered, from passive_churn → recovered, from fraud_flagged → recovered, and from recovered → raises `TransitionNotAllowed`.

- [x] **Task 10: Backend tests — `send_dunning_email` Celery task routing + bypass_engine_active** (AC: #1, #2)
  - [x] 10.1 Extend `backend/core/tests/test_tasks/test_notifications.py` (the file exists per Story 4.1 / 4.3 work — verify with `ls backend/core/tests/test_tasks/`; if absent, create). **Test invocation pattern:** call the task function synchronously (`send_dunning_email(failure.id, "update_payment")`) — DO NOT call `.delay(...)`. This mirrors every existing test in that file (e.g. `send_failure_notification(failure.id)` is called directly). Celery eager-mode is NOT globally configured in `safenet_backend/settings/*.py`; if a future test requires the broker layer specifically, set `app.conf.task_always_eager = True` in test setup (see `test_celery.py:28` for the pattern).
  - [x] 10.2 Tests to add:
    - `test_send_dunning_email_routes_update_payment_to_failure_email_builder` — patch `core.tasks.notifications.send_notification_email` to return `"resend_id_X"`. Call `send_dunning_email(failure.id, "update_payment")`. Assert `send_notification_email` was called once with `(subscriber, failure, account)`. Assert `NotificationLog` row with `email_type="update_payment"`, `status="sent"`, `resend_message_id="resend_id_X"`.
    - `test_send_dunning_email_routes_retry_reminder_to_failure_email_builder` — same, with `retry_reminder`.
    - `test_send_dunning_email_routes_final_notice_to_final_notice_email_builder` — patch `send_final_notice_email`. Call with `final_notice`. Assert that builder called, NOT `send_notification_email`.
    - `test_send_dunning_email_unknown_type_returns_silently` — call with `"banana"`. Assert no calls, no NotificationLog row.
    - `test_send_dunning_email_bypasses_engine_active_gate` — `account.engine_mode = None` (so `is_engine_active` returns False). Patch `send_notification_email`. Call task; assert builder still called and NotificationLog row created. Confirms Gate 1 bypass.
    - `test_send_dunning_email_still_runs_other_gates` — set `subscriber.email = ""`. Call task; assert builder NOT called and a `NotificationLog` row exists with `status="suppressed"` and `metadata={"reason": "no_email"}` (the `_log_suppression` helper writes the reason into the **NotificationLog** row's `metadata` JSONField — NOT into an `AuditLog.metadata` field). Confirms Gates 2–6 still active.
    - `test_send_dunning_email_audit_metadata_includes_trigger_client_manual` — happy path; assert `AuditLog` row with action=`"notification_sent"` has `metadata["trigger"] == "client_manual"`.
    - `test_existing_celery_tasks_unchanged_by_passes_gates_signature` — call `send_failure_notification(failure.id)` with `engine_mode=None` and assert it suppresses with reason=`"engine_not_active"` (i.e., the default `bypass_engine_active=False` preserves v0 behavior).
  - [x] 10.3 Run `cd backend && poetry run pytest core/tests/test_tasks/test_notifications.py core/tests/test_api/test_send_email.py core/tests/test_api/test_mark_resolved.py core/tests/test_models/test_subscriber_fsm.py -v` — all green.

### Frontend

- [x] **Task 11: Mount `<Toaster />` host so toasts actually render** (AC: #6)
  - [x] 11.1 The shadcn `Toaster` wrapper exists at `frontend/src/components/ui/sonner.tsx` but is NOT mounted anywhere in the app shell — `toast.error(...)` calls in `review-queue/page.tsx` and `activate/page.tsx` currently render nothing. AC6 (rate-limit toast) requires a mounted host. Edit `frontend/src/app/providers.tsx`:
    ```tsx
    import { Toaster } from "@/components/ui/sonner";
    // ...inside the return, ABOVE {children} closing:
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster richColors position="top-right" />
      </QueryClientProvider>
    </ThemeProvider>
    ```
    `richColors` enables sonner's per-status palette (success=green, error=red). `position="top-right"` aligns with non-blocking UX-DR8 reframed pattern (does not cover the row the user just clicked).

- [x] **Task 12: New mutation hook `useSendEmail`** (AC: #1, #2, #6)
  - [x] 12.1 Create `frontend/src/hooks/useSendEmail.ts`. Mirror the `useExcludeSubscriber.ts:11-26` shape:
    ```typescript
    "use client";

    import { useMutation, useQueryClient } from "@tanstack/react-query";
    import { AxiosError } from "axios";
    import api from "@/lib/api";
    import type { RecommendedEmailType } from "@/types/failed_payment";

    export type SendableEmailType = Exclude<RecommendedEmailType, null>;

    export interface SendEmailVariables {
      subscriberId: number;
      failureId: number;
      emailType: SendableEmailType;
    }

    interface SendEmailResult {
      queued: boolean;
      email_type: SendableEmailType;
      failure_id: number;
    }

    export interface SendEmailErrorEnvelope {
      code: string;
      message: string;
      field: string | null;
    }

    export class SendEmailError extends Error {
      readonly code: string;
      readonly field: string | null;
      readonly status: number;
      readonly retryAfterSeconds: number | null;
      constructor(envelope: SendEmailErrorEnvelope, status: number, retryAfter: string | null) {
        super(envelope.message);
        this.code = envelope.code;
        this.field = envelope.field;
        this.status = status;
        this.retryAfterSeconds = retryAfter ? parseInt(retryAfter, 10) || null : null;
      }
    }

    export function useSendEmail() {
      const queryClient = useQueryClient();
      return useMutation<SendEmailResult, SendEmailError, SendEmailVariables>({
        mutationFn: async ({ subscriberId, failureId, emailType }) => {
          try {
            const { data } = await api.post<{ data: SendEmailResult }>(
              `/subscribers/${subscriberId}/send-email/`,
              { email_type: emailType, failure_id: failureId },
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
        },
      });
    }
    ```
    Custom `SendEmailError` surfaces `code` (so the consumer can branch on `RATE_LIMITED` / `OPT_OUT` / `EXCLUDED` / `DPA_REQUIRED`) and `retryAfterSeconds` (parsed from the `Retry-After` header) without exposing axios internals to the component.

- [x] **Task 13: New mutation hook `useMarkResolved`** (AC: #3)
  - [x] 13.1 Create `frontend/src/hooks/useMarkResolved.ts`:
    ```typescript
    "use client";

    import { useMutation, useQueryClient } from "@tanstack/react-query";
    import api from "@/lib/api";

    interface MarkResolvedResult {
      resolved: boolean;
      subscriber_id: number;
      from_status: string;
      to_status: "recovered";
    }

    export function useMarkResolved() {
      const queryClient = useQueryClient();
      return useMutation<MarkResolvedResult, Error, number>({
        mutationFn: async (subscriberId) => {
          const { data } = await api.post<{ data: MarkResolvedResult }>(
            `/subscribers/${subscriberId}/mark-resolved/`,
          );
          return data.data;
        },
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ["failed-payments"] });
          queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
        },
      });
    }
    ```
    Invalidate both `failed-payments` (so the row's badge re-renders) and `["dashboard", "summary"]` (so KPI cards re-aggregate). **CRITICAL:** the dashboard-summary query key is the two-element array `["dashboard", "summary"]`, NOT the single string `["dashboard-summary"]` — see `frontend/src/hooks/useDashboardSummary.ts:10` and the existing pattern in `useExcludeSubscriber.ts:23`.

- [x] **Task 14: Extend `useExcludeSubscriber` to invalidate `["failed-payments"]`** (AC: #4)
  - [x] 14.1 Edit `frontend/src/hooks/useExcludeSubscriber.ts:21-24`. Add one line to `onSuccess`:
    ```typescript
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions", "pending"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      queryClient.invalidateQueries({ queryKey: ["failed-payments"] });   // NEW for Story 3.3 v1
    },
    ```
    The existing review-queue caller is unaffected — it doesn't use `["failed-payments"]`.

- [x] **Task 15: Rewrite `ActionButtons` and lift the placeholder gate in `FailedPaymentsList`** (AC: #1, #2, #3, #4, #6, #7)
  - [x] 15.1 Edit `frontend/src/components/dashboard/FailedPaymentsList.tsx`. The current `ActionButtons` (lines 148-171) renders 3 disabled Ghost buttons. Replace with a wired implementation:
    ```tsx
    import {
      DropdownMenu,
      DropdownMenuContent,
      DropdownMenuItem,
      DropdownMenuTrigger,
    } from "@/components/ui/dropdown-menu";
    import { ChevronDownIcon } from "lucide-react";
    import { toast } from "sonner";
    import { useSendEmail, SendEmailError, type SendableEmailType } from "@/hooks/useSendEmail";
    import { useMarkResolved } from "@/hooks/useMarkResolved";
    import { useExcludeSubscriber } from "@/hooks/useExcludeSubscriber";

    const SPECIFIC_EMAIL_OPTIONS: Array<{ type: SendableEmailType; label: string }> = [
      { type: "update_payment", label: "Update payment" },
      { type: "retry_reminder", label: "Retry reminder" },
      { type: "final_notice", label: "Final notice" },
    ];

    function ActionButtons({
      row,
      gateDisabled,
      gateTooltip,
    }: {
      row: FailedPayment;
      gateDisabled: boolean;
      gateTooltip: string | undefined;
    }) {
      const sendEmail = useSendEmail();
      const markResolved = useMarkResolved();
      const exclude = useExcludeSubscriber();

      const sendingEmailType = sendEmail.isPending
        ? sendEmail.variables?.emailType ?? null
        : null;
      const isPending = sendEmail.isPending || markResolved.isPending || exclude.isPending;
      const sendDisabled = gateDisabled || isPending;
      const recommendedDisabled = sendDisabled || row.recommended_email_type === null;

      const handleSend = (emailType: SendableEmailType) => {
        sendEmail.mutate(
          { subscriberId: row.subscriber_id, failureId: row.id, emailType },
          {
            onSuccess: () => {
              toast.success(`Queued ${labelFor(emailType)} email.`);
            },
            onError: (err) => {
              if (err.code === "RATE_LIMITED") {
                const seconds = err.retryAfterSeconds ?? 60;
                toast.error(`Rate limit reached. Try again in ${seconds}s.`, { duration: 6000 });
              } else if (err.code === "OPT_OUT") {
                toast.error("Subscriber has opted out of notifications.", { duration: 6000 });
              } else if (err.code === "EXCLUDED") {
                toast.error("Subscriber is excluded from automation.", { duration: 6000 });
              } else if (err.code === "DPA_REQUIRED") {
                toast.error("Sign the DPA to enable email sends.", { duration: Infinity });
              } else {
                toast.error(err.message || "Failed to queue email.", { duration: 6000 });
              }
            },
          },
        );
      };

      const handleMarkResolved = () => {
        markResolved.mutate(row.subscriber_id, {
          onSuccess: () => toast.success("Marked as resolved."),
          onError: () => toast.error("Failed to mark resolved.", { duration: 6000 }),
        });
      };

      const handleExclude = () => {
        exclude.mutate(row.subscriber_id, {
          onSuccess: () => toast.success("Excluded from future recommendations."),
          onError: () => toast.error("Failed to exclude subscriber.", { duration: 6000 }),
        });
      };

      return (
        <div className="flex justify-end gap-1">
          <Button
            size="sm"
            variant="default"
            disabled={recommendedDisabled}
            title={
              row.recommended_email_type === null
                ? "No recommendation available yet"
                : gateTooltip
            }
            onClick={() =>
              row.recommended_email_type !== null && handleSend(row.recommended_email_type)
            }
            aria-label="Send recommended"
          >
            {sendingEmailType !== null && sendingEmailType === row.recommended_email_type
              ? "Sending…"
              : "Send recommended"}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="sm"
                variant="ghost"
                disabled={sendDisabled}
                title={gateTooltip}
                aria-label="Send specific email"
              >
                <ChevronDownIcon className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {SPECIFIC_EMAIL_OPTIONS.map((opt) => (
                <DropdownMenuItem
                  key={opt.type}
                  disabled={sendDisabled}
                  onSelect={() => handleSend(opt.type)}
                >
                  {opt.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <Button
            size="sm"
            variant="ghost"
            disabled={sendDisabled}
            title={gateTooltip}
            aria-label="Mark resolved"
            onClick={handleMarkResolved}
          >
            Mark resolved
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={sendDisabled}
            title={gateTooltip}
            aria-label="Exclude"
            onClick={handleExclude}
          >
            Exclude
          </Button>
        </div>
      );
    }

    function labelFor(t: SendableEmailType): string {
      return SPECIFIC_EMAIL_OPTIONS.find((o) => o.type === t)?.label ?? t;
    }
    ```
  - [x] 15.2 Update `PaymentRow` to pass `row` instead of the old `disabled`/`tooltip` props. Replace the `ActionButtons` invocation in `PaymentRow` (currently `<ActionButtons disabled={actionsDisabled} tooltip={actionsTooltip} />` at line 221) with `<ActionButtons row={row} gateDisabled={gateDisabled} gateTooltip={gateTooltip} />`.
  - [x] 15.3 Remove the `actionsDisabled = true` line and the `Stories 3.3/3.4 lift the placeholder gate` comment block at `FailedPaymentsList.tsx:236-242`. Replace with:
    ```tsx
    // Tooltip precedence: tier > DPA. Story 3.3 v1 wires real mutations;
    // each per-row mutation hook surfaces its own pending state and toast.
    let gateTooltip: string | undefined = undefined;
    if (isFree) {
      gateTooltip = TIER_TOOLTIP;
    } else if (sendDisabled && dpaTooltip) {
      gateTooltip = dpaTooltip;
    }
    const gateDisabled = isFree || sendDisabled;
    ```
    Drop the now-unused `PLACEHOLDER_TOOLTIP` constant. Update the `PaymentRow` props plumbing accordingly.
  - [x] 15.4 Update the `PaymentRow` component signature to accept `gateDisabled` + `gateTooltip` instead of `actionsDisabled` + `actionsTooltip`. The render-loop at line 305-311 changes correspondingly.
  - [x] 15.5 Subscriber name + email cell (lines 190-201) is unchanged — Story 3.2 v1's review patch (line 344) already fixed the duplicate-email bug.

- [x] **Task 16: Frontend tests — `useSendEmail` hook + error envelope handling** (AC: #1, #2, #5, #6)
  - [x] 16.1 Create `frontend/src/__tests__/useSendEmail.test.ts`. Pattern in `frontend/src/__tests__/useDpaGate.test.ts` (existing) for hook testing with `QueryClientProvider`. Use `vi.mock("@/lib/api", () => ...)` to stub axios.
  - [x] 16.2 Tests:
    - `posts to the correct URL with snake_case body` — mock `api.post`. Call `mutate({subscriberId: 7, failureId: 42, emailType: "update_payment"})`. Assert `api.post` called with `("/subscribers/7/send-email/", {email_type: "update_payment", failure_id: 42})`.
    - `invalidates ["failed-payments"] on success` — mock `api.post` to resolve. Spy on `queryClient.invalidateQueries`. Call mutate; await success. Assert invalidation was called with `{queryKey: ["failed-payments"]}`.
    - `wraps 429 axios error into SendEmailError with retryAfterSeconds` — mock `api.post` to reject with `AxiosError({response: {status: 429, data: {error: {code: "RATE_LIMITED", message: "...", field: null}}, headers: {"retry-after": "42"}}})`. Assert thrown error has `code === "RATE_LIMITED"` and `retryAfterSeconds === 42`.
    - `wraps 422 OPT_OUT into SendEmailError` — mock with 422 body. Assert `code === "OPT_OUT"`, `retryAfterSeconds === null`.
    - `wraps 403 DPA_REQUIRED into SendEmailError` — mock with 403 body. Assert `code === "DPA_REQUIRED"`.
    - `null retry-after header parses as null` — 429 response with NO `retry-after` header → `retryAfterSeconds === null`.
    - `non-numeric retry-after parses as null` — `retry-after: "soon"` → `retryAfterSeconds === null`.

- [x] **Task 17: Frontend tests — `FailedPaymentsList` Story 3.3 v1 additions** (AC: #1, #2, #3, #4, #6, #7)
  - [x] 17.1 Edit `frontend/src/__tests__/FailedPaymentsList.test.tsx` (existing). Add mocks for the 3 new hooks at the top of the file alongside the existing `vi.mock` block:
    ```typescript
    const mockSendEmailMutate = vi.fn();
    const mockMarkResolvedMutate = vi.fn();
    const mockExcludeMutate = vi.fn();
    vi.mock("@/hooks/useSendEmail", async () => {
      const actual = await vi.importActual<typeof import("@/hooks/useSendEmail")>("@/hooks/useSendEmail");
      return {
        ...actual,
        useSendEmail: () => ({
          mutate: mockSendEmailMutate,
          isPending: false,
          variables: undefined,
        }),
      };
    });
    vi.mock("@/hooks/useMarkResolved", () => ({
      useMarkResolved: () => ({ mutate: mockMarkResolvedMutate, isPending: false }),
    }));
    vi.mock("@/hooks/useExcludeSubscriber", () => ({
      useExcludeSubscriber: () => ({ mutate: mockExcludeMutate, isPending: false }),
    }));
    ```
    Reset all three in `beforeEach`. Note `await vi.importActual` to preserve the `SendableEmailType` and `SendEmailError` exports — the component imports both.
  - [x] 17.2 Update existing test `Mid tier with DPA accepted shows placeholder tooltip` (line ~272) — rename to `Mid tier with DPA accepted enables Send recommended only when recommendation present` and split:
    - When `recommended_email_type === null` → "Send recommended" button is disabled with title "No recommendation available yet".
    - When `recommended_email_type === "update_payment"` → button is enabled, title is undefined; clicking calls `mockSendEmailMutate` with `{subscriberId, failureId, emailType: "update_payment"}`.
  - [x] 17.3 Add new tests:
    - `Send recommended button calls useSendEmail with row's recommended_email_type` — row with `recommended_email_type="update_payment"`. Click button; assert `mockSendEmailMutate.mock.calls[0][0]` equals `{subscriberId: row.subscriber_id, failureId: row.id, emailType: "update_payment"}`.
    - `dropdown opens with three Send specific options and each dispatches the right type` — click the dropdown trigger (button with aria-label "Send specific email"). Use `screen.getByRole("menuitem", {name: /Update payment/})` to find each. Click each → assert mutate calls with corresponding email_type.
    - `Mark resolved button calls useMarkResolved` — click the row's Mark resolved → assert `mockMarkResolvedMutate` called with `row.subscriber_id`.
    - `Exclude button calls useExcludeSubscriber` — click Exclude → assert `mockExcludeMutate` called with `row.subscriber_id`.
    - `Free tier disables all 4 controls with tier tooltip` — Free tier; assert Send recommended, dropdown trigger, Mark resolved, Exclude all `disabled` and have title "Upgrade to Mid or Pro to enable email actions". The dropdown trigger is also disabled (don't open menu when gated).
    - `Mid tier without DPA disables all 4 controls with DPA tooltip` — same shape with the DPA tooltip "Sign the DPA to enable email sends".
    - `Sending… label appears on the recommended button while mutation is pending` — re-mock `useSendEmail` to return `{isPending: true, variables: {emailType: "update_payment", subscriberId: row.subscriber_id, failureId: row.id}}`. Render row with `recommended_email_type="update_payment"`. Assert button text is "Sending…" and button is disabled.
  - [x] 17.4 The existing tests for `recommended email chip shows em-dash for null type`, `applies amber border to fraud-flagged rows`, and the sort-header tests are unchanged.
  - [x] 17.5 Run `cd frontend && pnpm vitest run FailedPaymentsList useSendEmail` — all green.

- [x] **Task 18: Frontend tests — toast on rate limit (integration)** (AC: #6)
  - [x] 18.1 Add a test in `FailedPaymentsList.test.tsx` that mocks `useSendEmail` to invoke `onError` with a `SendEmailError`-shaped object (`{code: "RATE_LIMITED", retryAfterSeconds: 42, message: "..."}`). Mock the `sonner` module:
    ```typescript
    const mockToastError = vi.fn();
    const mockToastSuccess = vi.fn();
    vi.mock("sonner", () => ({
      toast: { error: mockToastError, success: mockToastSuccess, warning: vi.fn() },
    }));
    ```
    Click "Send recommended"; the mocked `mutate` immediately invokes the supplied `onError` callback with the rate-limit error. Assert `mockToastError` called with `"Rate limit reached. Try again in 42s."` and `{duration: 6000}`.
  - [x] 18.2 Repeat for `OPT_OUT`, `EXCLUDED`, `DPA_REQUIRED`, and an unknown code (falls back to `err.message`).

### Cross-cutting

- [ ] **Task 19: Manual smoke verification** (AC: all) — _Deferred to reviewer; the automated suite covers ACs 1–7._
  - [ ] 19.1 `docker compose up`. Seed a Mid-tier account with DPA accepted (use the seed user from 3-1-v1's manual verification). Seed at least 3 SubscriberFailures via Django shell:
    ```bash
    docker compose exec backend poetry run python manage.py shell
    ```
    ```python
    from django.utils import timezone
    from core.models.account import Account
    from core.models.subscriber import Subscriber, SubscriberFailure
    a = Account.objects.first()
    s1 = Subscriber.objects.create(account=a, stripe_customer_id="cus_smoke_3", email="alice@example.com")
    f1 = SubscriberFailure.objects.create(account=a, subscriber=s1, payment_intent_id="pi_smoke_3", decline_code="insufficient_funds", amount_cents=4500, classified_action="retry_notify", failure_created_at=timezone.now())
    ```
  - [ ] 19.2 In the browser:
    - Open `/dashboard`. Confirm the row renders with **Send recommended** disabled (`recommended_email_type is null` until 3.5 ships) and the dropdown chevron + Mark resolved + Exclude buttons enabled.
    - Click the dropdown chevron → 3 options visible. Click "Update payment" → success toast "Queued Update payment email.". Reload — `last_email_sent_at` re-renders as a relative time.
    - Click "Mark resolved" → success toast "Marked as resolved." → row's status badge changes to Recovered.
    - Click "Exclude" → success toast → row's recommended-email column eventually reads "—" (after 3.5 ships).
    - Trigger 11 sends in 60s (use a small JS console loop) → 11th surfaces "Rate limit reached. Try again in <N>s.".
  - [ ] 19.3 Switch the user's tier to `free` via shell → confirm all four per-row controls are disabled with the tier tooltip, the inline upgrade banner remains, and POSTing to `/send-email/` directly via curl returns 403 `TIER_REQUIRED`.

### Review Findings

_Appended 2026-04-30 by `/bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor). 32 raw findings → 3 patch / 3 decision-needed / 16 defer / 10 dismissed._

**Patch (unambiguous fixes):**

- [x] [Review][Patch] `isinstance(failure_id, int)` accepts booleans — `True`/`False` pass the check and coerce to id 0/1. Add `not isinstance(failure_id, bool)`. [`backend/core/views/send_email.py:80`]
- [x] [Review][Patch] Concurrent `mark_resolved` race — read-then-write with no row lock; two simultaneous calls both read `prior_status=active`, both transition. Wrap fetch+transition+save in `transaction.atomic()` with `select_for_update()`. [`backend/core/views/send_email.py:185-205`]
- [x] [Review][Patch] `post_transition` audit fires before `subscriber.save()` — if save raises, audit row claims `status_recovered` but DB stays at prior status (split-brain). Wrap signal-emitting transition + save in the same `transaction.atomic()` block as the patch above. [`backend/core/models/subscriber.py:102-114`, `backend/core/views/send_email.py:195-205`]
- [x] [Review][Patch] Reject `/send-email/` for non-active subscriber statuses — `update_payment` and `retry_reminder` currently send to `recovered`/`passive_churn`/`fraud_flagged` subscribers. Add a status check at the view returning `422 INVALID_STATE`, symmetric with `final_notice`'s Gate 6. (Resolved D1.) [`backend/core/views/send_email.py:42-156`]
- [x] [Review][Patch] Throttle `/mark-resolved/` at 10/min/account — sibling endpoint parity. Add new `_MarkResolvedThrottle` with scope `"mark_resolved"`, register in `DEFAULT_THROTTLE_RATES`, and add a `_THROTTLED_MESSAGES` entry. (Resolved D2.) [`backend/core/views/send_email.py:159-223`, `backend/safenet_backend/settings/base.py`, `backend/core/views/errors.py`]
- [x] [Review][Patch] Unify query-invalidation across mutation hooks — `useSendEmail`, `useMarkResolved`, and `useExcludeSubscriber` all invalidate `["failed-payments"]` + `["dashboard","summary"]`. Drop `["actions","pending"]` from `useExcludeSubscriber` (v0 review-queue is quarantined). (Resolved D3.) [`frontend/src/hooks/useSendEmail.ts`, `frontend/src/hooks/useMarkResolved.ts`, `frontend/src/hooks/useExcludeSubscriber.ts`]

**Deferred (pre-existing or out-of-scope, see `_bmad-output/deferred-work.md` for reasons):**

- [x] [Review][Defer] Duplicate-send race in `send_dunning_email` (Resend called before NotificationLog write) — pattern shared with all three pre-existing notification tasks. [`backend/core/tasks/notifications.py:424-449`]
- [x] [Review][Defer] `_throttled_message` picks first scoped throttle class arbitrarily — works today (one throttle per view), fragile if stacked. [`backend/core/views/errors.py:13-21`]
- [x] [Review][Defer] `request.user.account` missing returns 404 not 403 — matches existing convention prescribed by the spec. [`backend/core/views/send_email.py:46,165`]
- [x] [Review][Defer] `test_password_reset.py` 429 message regression — Story 4.5 owns the password-reset surface. [`backend/core/tests/test_api/test_password_reset.py`]
- [x] [Review][Defer] Migration 0017 (auditlog actor) unrelated to Story 3.3 — Sabri-approved per Debug Log; bisect hazard if 4.4 rolls back. [`backend/core/migrations/0017_alter_auditlog_actor.py`]
- [x] [Review][Defer] `useMarkResolved` error type is `Error`, not envelope-typed — INVALID_TRANSITION code never surfaced in toast.
- [x] [Review][Defer] `useSendEmail`/`useMarkResolved` don't invalidate `["actions","pending"]` like `useExcludeSubscriber` does — covered by D3 above.
- [x] [Review][Defer] Cross-action lockout in `ActionButtons` — any pending mutation disables all four buttons. [`frontend/src/components/dashboard/FailedPaymentsList.tsx:183-184`]
- [x] [Review][Defer] No test for throttle window reset (60s elapse → 11th passes). [`backend/core/tests/test_api/test_send_email.py`]
- [x] [Review][Defer] `_throttled_message` `scope = None` initialization fragility — works today. [`backend/core/views/errors.py:15-21`]
- [x] [Review][Defer] `labelFor` falls back to raw type string — minor i18n leak if backend adds new types.
- [x] [Review][Defer] `retry-after` header uses bracket access — works with Axios's lowercase normalization. [`frontend/src/hooks/useSendEmail.ts`]
- [x] [Review][Defer] Dropdown mock in tests bypasses Radix focus/keyboard semantics — a11y test gap. [`frontend/src/__tests__/FailedPaymentsList.test.tsx`]
- [x] [Review][Defer] DPA-error toast uses `duration: Infinity` — multiple clicks stack non-dismissable toasts. [`frontend/src/components/dashboard/FailedPaymentsList.tsx:207`]
- [x] [Review][Defer] `bypass_engine_active=True` future-misuse if `send_dunning_email.delay()` gets new callers. [`backend/core/tasks/notifications.py:414-419`]
- [x] [Review][Defer] Subscriber with empty email returns 202 then task-suppresses silently — view should arguably 422 NO_EMAIL.

## Dev Notes

### v1 Scope Boundaries (READ FIRST)

- **In scope:** new `POST /send-email/` view, new `POST /mark-resolved/` view, new `send_dunning_email` Celery task (router for the 3 client-manual email types), `mark_resolved_manually` FSM transition, `bypass_engine_active` flag on `_passes_gates`, frontend mutation hooks + per-row UI wiring, rate-limit throttle scope, toast surfacing.
- **Out of scope:**
  - Bulk multi-row send (Story 3.4 v1).
  - Recommendation rule engine that populates `recommended_email_type` (Story 3.5 v1) — until 3.5 lands, the "Send recommended" button is always disabled because the field is always `null`. The wiring in this story is correct so 3.5 is a one-line backend flip.
  - Daily polling job that auto-transitions Active → Recovered / Passive Churn (Story 3.4 v1 includes this).
  - New email templates / copy (Story 4.x ships templates; this story only adds new `email_type` choices that share the existing `failure_notice` template body for `update_payment` + `retry_reminder`, and the existing `final_notice` template body for `final_notice`). Copy differentiation between "update_payment" and "retry_reminder" is a v2 concern (`epics.md` does NOT mandate distinct bodies for v1 — only distinct triggers and audit trails).
  - Recovery confirmation email on manual-resolve (`recovery_confirmation` is engine-driven via Story 3.4 polling; manual-resolve is silent).
  - Per-account timezone (still UTC, deferred from 3.2 v1).

### Architecture Compliance

- **Tenant isolation:** all queries via `for_account(account.id)` from `TenantScopedModel.objects` (`models/base.py:13-15`). Never `.objects.all()`. [Source: architecture.md#Enforcement Guidelines:594-610]
- **API response envelope:** `{"data": ...}` for success, `{"error": {code, message, field}}` for errors. Never bare. [Source: architecture.md#Format Patterns:489-510]
- **Field naming:** snake_case in API + TS interfaces. `email_type`, `failure_id`, `subscriber_id`, `from_status`, `to_status`. No camelCase. [Source: architecture.md#Naming Patterns:415-427]
- **API URL pattern:** kebab-case multi-word: `/send-email/`, `/mark-resolved/`. [Source: architecture.md#Naming Patterns:410]
- **DPA gate first:** every dunning send-capable endpoint must call `require_dpa_accepted(account)` BEFORE tenant scoping or body validation, per `core/services/dpa.py:25-43` docstring and 3-1-v1 AC1. Story 3.3 explicitly orders gates per Task 5.3.
- **Error handling by layer:** view returns DRF Response with the error envelope; the custom exception handler at `core/views/errors.py:9-31` maps `Throttled` → `RATE_LIMITED` envelope. The frontend axios interceptor extracts `error.response.data.error`; the new `SendEmailError` wrapper in `useSendEmail` exposes `code` + `retryAfterSeconds` to consumers.
- **TanStack Query for server data; mutations invalidate.** Every mutation in this story invalidates `["failed-payments"]` so the dashboard re-fetches and the UI converges on server truth. `useMarkResolved` additionally invalidates `["dashboard", "summary"]` (two-element array — see `frontend/src/hooks/useDashboardSummary.ts:10`; passing the single string `["dashboard-summary"]` would silently no-op). [Source: architecture.md#Process Patterns:581-590]
- **No business logic in views beyond gating + dispatch.** The view's job is gate + validate + enqueue + audit. The Celery task owns delivery. [Source: architecture.md#Structure Patterns:477]
- **Audit-event verbs:** `email_sent` (client-manual dispatch intent), `email_sent_blocked` (gate rejection), `manual_resolved` (FSM mutation by client), `notification_sent` (delivery success — engine-actor, written by the Celery task; existing). The post_transition signal continues writing `status_recovered`. Three actors will appear on a successful manual-resolve trace: engine (`status_recovered`), client (`manual_resolved`). **`email_sent` and `email_sent_blocked` are NEW verbs introduced by Story 3.3 v1** — `AuditLog.action` is a free-form CharField, so no migration or enum update is required.
- **Celery task idempotency:** the partial unique constraint on `(failure, email_type) WHERE status="sent"` (`notification.py:47-51`) is the source of truth for "send at most once per (failure, email_type)". A duplicate `update_payment` send for the same failure logs `duplicate_race` and exits gracefully — same pattern as Story 4.3. NOT: defer-and-suppress at the view layer. The view is intentionally permissive; the constraint is the floor.

### Technical Requirements

- **`is_engine_active` is quarantined-but-still-imported.** Per Story 3.1 v1's Task 4, `core/services/tier.py:23-30` retains `is_engine_active(account)` as legacy v0 behavior. The existing 3 Celery tasks (`send_failure_notification`, `send_final_notice`, `send_recovery_confirmation`) still call it via Gate 1 and that's fine — they're the path the v0 polling code uses. The new `send_dunning_email` task explicitly opts out via `bypass_engine_active=True`. **DO NOT** remove `is_engine_active` in this story; the Sprint Change Proposal §3.2 quarantine pass owns that cleanup.
- **Throttle scoping.** `ScopedRateThrottle` keys on the user identity for authenticated requests (per DRF's `get_cache_key` impl). Since each user owns one account in v1, "10/min per user" is effectively "10/min per account". Multi-user-per-account is an NFR-SC3 future concern — `ScopedRateThrottle` will need a custom `get_cache_key` that hashes on `account.id` once Memberships ship. **DO NOT** preemptively switch to account-keyed throttling in this story — the multi-user model isn't on `main`. [Source: backend/core/models/account.py:34-38 — "future Membership join table"]
- **DRF 429 envelope.** When `_SendEmailThrottle` rejects, DRF raises `Throttled(wait=N)`. The custom exception handler at `core/views/errors.py:18-19` already maps to `code=RATE_LIMITED`; Task 7.3 adds the per-scope message. The `Retry-After` header is set automatically by DRF (`Throttled.wait` is read by `set_rollback`). Frontend reads via `error.response.headers["retry-after"]` (axios lowercases header keys).
- **Opt-out check at view boundary.** The Celery task's Gate 4 also runs the opt-out check — that's defense in depth; the view-level check exists so the **client** sees a clear `422 OPT_OUT` rather than a silent suppression. Both audits coexist: the view writes `email_sent_blocked` (actor=client), the task would have written `notification_suppressed` (actor=engine) had it run.
- **Asymmetry to NOT "fix":** the **view-level** opt-out check uses `NotificationOptOut.objects.for_account(account.id).filter(...)` (tenant-scoped via `TenantScopedModel`). The **Gate 4** lookup inside `_passes_gates` (`backend/core/tasks/notifications.py:64-67`) uses bare `.filter(account=account)` — NOT scoped via `for_account`. Both are correct in context (the task already received an `account`-bound failure object), but a dev who notices the inconsistency may be tempted to swap Gate 4 to `for_account` and break the existing `test_optout.py` assertions. **Leave Gate 4 as-is.** This story does NOT modify `_passes_gates` Gates 2–6.
- **`mark_resolved_manually` source list.** Source must be `[STATUS_ACTIVE, STATUS_PASSIVE_CHURN, STATUS_FRAUD_FLAGGED]`. Including `STATUS_RECOVERED` would make the call idempotent, but AC3 explicitly mandates `400 INVALID_TRANSITION` for already-recovered subscribers — this surfaces a hint that the UI is showing stale data and forces a refetch.
- **Existing tests for `failed_payments_list` use `auth_client`** from `backend/core/tests/conftest.py:30-38` (project-level conftest). Use the same fixture; do not invent a new auth fixture per test file.
- **Existing email-builder service is reusable as-is.** `send_notification_email` and `send_final_notice_email` accept `(subscriber, failure, account)` — Story 3.3's `send_dunning_email` task calls them unchanged. We do NOT need new email templates for `update_payment` or `retry_reminder` in v1 (`epics.md:947-967` covers v1 mapping; the body differentiation is a v2 concern).
- **`subscribers/{id}/exclude/` already exists.** Story 3.3 reuses it; do NOT create a parallel endpoint. The frontend `useExcludeSubscriber` hook is similarly reused with one extra `invalidateQueries` line.
- **shadcn DropdownMenu primitive.** `frontend/src/components/ui/dropdown-menu.tsx` is already in the repo and consumed by `UserMenu.tsx`. Use the same composition: `<DropdownMenu>` → `<DropdownMenuTrigger asChild>` (wrapping a `<Button>`) → `<DropdownMenuContent align="end">` with `<DropdownMenuItem>` children. Do NOT introduce a popover or build a custom dropdown.
- **Sonner Toaster mount is missing on `main`.** Per Task 11, this story mounts `<Toaster />` in `providers.tsx`. This is a 5-line additive change that benefits the existing `toast.error/success` calls in `review-queue/page.tsx` and `activate/page.tsx` (currently no-ops).

### UX Design Requirements

- **Per-row controls are dense.** Four per-row controls (Send recommended + dropdown + Mark resolved + Exclude) is intentional. Use `size="sm"` and `variant="ghost"` for the auxiliary actions; `variant="default"` for "Send recommended" so the primary action visually anchors the row. [Source: ux-design-specification.md#12.1:1040-1056 — One Primary CTA per row]
- **Loading-state defaults.** While any per-row mutation is pending, ALL four buttons in that row are disabled (single-flight per row — a user shouldn't be able to mark-resolved while a send is enqueueing). Implementation: `isPending = sendEmail.isPending || markResolved.isPending || exclude.isPending` is the per-row gate. Carries forward the 3-1-v1 "loading-state default" review theme (line 454-456 of 3-2-v1).
- **Toast positioning.** `position="top-right"` (Task 11). Does not occlude the row the user just clicked. Sonner `richColors` distinguishes success (green) from error (red). [Source: ux-design-specification.md UX-DR8 reframed]
- **Toast duration.**
  - Success: default (4s).
  - Recoverable error (rate-limit, opt-out, exclusion): `duration: 6000` (6s — long enough to read).
  - Blocking error (DPA missing): `duration: Infinity` (require dismiss — the user must navigate away to fix).
  Mirror the existing `review-queue/page.tsx:48-103` and `activate/page.tsx:50` durations exactly.
- **Empty-row dropdown.** The "Send specific" dropdown ALWAYS lists all 3 options regardless of recommendation — the dropdown is the user's escape hatch when they disagree with the recommendation. AC2 mandates exactly these 3 options in this exact order: Update payment, Retry reminder, Final notice. Do NOT reorder.
- **"Send recommended" disabled copy.** When `recommended_email_type === null`, the button title is `"No recommendation available yet"` (NOT the tier or DPA tooltip). Recommendation absence is orthogonal to gating.
- **Tooltip precedence (carry-forward from 3-1-v1 → 3-2-v1):** tier > DPA > placeholder-removed. Story 3.3 drops the placeholder entirely (the buttons now do work). Free tier still wins; DPA-pending falls through to the DPA tooltip.
- **Pending UI affordance.** The "Send recommended" button label reads `"Sending…"` while `sendEmail.isPending && variables.emailType === recommended_email_type`. The other 3 buttons just read `disabled` (no spinner) — they're ghost buttons; a label change would be more disruptive than a disabled state.

### Previous Story Intelligence

From Story 3-2-v1 (current-month dashboard, just shipped):
- **Action button placeholders + tier tooltip precedence is in place.** Story 3.3 lifts the `actionsDisabled = true` gate and the placeholder constant; the precedence chain (tier > DPA > [placeholder removed]) is preserved. The Free-tier inline upgrade banner above the table (Task 6.3 of 3-2-v1) stays unchanged.
- **`["failed-payments"]` query key is the canonical cache key.** Hooks invalidate this key on send/resolve/exclude.
- **Native `title` attribute is the project's tooltip surface.** No `@base-ui/react` Tooltip wrapper — Story 3-2-v1 deferred that. Tests assert via `getAttribute("title")`. Match.
- **Adversarial review themes from 3-1-v1 / 3-2-v1 to pre-empt:**
  - **Tenant defense-in-depth on subqueries** — `NotificationOptOut.objects.for_account(account.id).filter(...)` in Task 5.3, NOT bare `NotificationOptOut.objects.filter(...)`. Story 3-2-v1 review patches (line 336-337) flagged the same pattern.
  - **Error envelope `field` always present.** All 400 responses include `field` (`"email_type"`, `"failure_id"`, or `null`).
  - **DPA gate before validation.** A malformed payload from an unsigned account returns `DPA_REQUIRED`, not `VALIDATION_ERROR`. Test asserts both — see Task 8.2 `test_free_tier_returns_403`.
  - **Subscriber email may be empty.** The opt-out check guards with `if sub_email and ...` so an empty `subscriber.email` doesn't flag every account-level NotificationOptOut row. Mirrors the Gate 2 (`no_email`) pattern in `_passes_gates`.
  - **Loading-state safe defaults.** `useSendEmail.isPending` blocks all per-row controls — a "send" enabled mid-mutation is not safe.
- **`useExcludeSubscriber` is the canonical exclude hook.** Don't build a parallel one; extend it with one invalidation line.

From Story 3-1-v1 (DPA gate):
- **`require_dpa_accepted` returns either a 403 Response or None.** Pattern: `dpa_response = require_dpa_accepted(account); if dpa_response is not None: return dpa_response`. Match exactly.
- **DPA version `"v1.0-2026-04-29"`** is the current; v0 carry-forward as `"v0-legacy"`. Tests should set up both fixtures via `dpa_accepted_at = timezone.now()` + `dpa_version = CURRENT_DPA_VERSION`.

From Story 4.3 (final notice + recovery confirmation):
- **`send_final_notice_email` and `send_notification_email` are the email-builder service entry points.** Both are synchronous (raise `SkipNotification` / `EmailConfigurationError` / `Exception`); the Celery task wraps with retry/DLL machinery. Story 3.3's `send_dunning_email` reuses the same wrapper pattern.
- **The partial unique constraint on NotificationLog `(failure, email_type) WHERE status='sent'`** is the deduplication source of truth. Story 4.3 review hardened this; Story 3.3 inherits it and adds the new `update_payment` / `retry_reminder` types as additional unique-keys (a single failure can have 4 distinct `sent` rows: failure_notice + update_payment + retry_reminder + final_notice). That's intentional — different message intents, different dedup keys.

From Story 4.4 (opt-out):
- **`NotificationOptOut` is per (subscriber_email, account_id), case-insensitive on email.** Use `subscriber_email__iexact=sub.email.strip().lower()`. The model uses `EmailField` (already lowercase-canonicalized at storage but defense-in-depth is cheap). Story 4.4 confirmed this is on `main`.

### Git Intelligence

Recent commits (`git log --oneline -8`):
- `4a592ad` Merge pull request #3 (3-2-v1 done) — the immediate parent for this work.
- `8a647d0` Status: done (sprint-status update for 3-2-v1).
- `01e1026` Merge pull request #2 (3-1-v1 done).
- `7f270c4` Status: done (sprint-status update for 3-1-v1).
- `f366d31` Major rescoping — v1 commit-of-record.
- `6fe105e` Backend (8 files) — Story 4.5 password-reset hardening (sets the `_THROTTLED_MESSAGE` pattern Task 7.3 generalizes).
- `a23988e` Story 4.3: final notice & recovery confirmation emails.
- `bc1f1ec` Story 4.4: opt-out mechanism (NotificationOptOut model).

**Implication:** Stories 3.1 v1 and 3.2 v1 are merged. Story 4.x stories are merged. Story 3.3 builds directly on the patterns established by 3-1-v1 (DPA gate) and 3-2-v1 (failed-payments list + action button placeholders). Quarantined v0 code (`is_engine_active`, `engine_mode` field, supervised-mode review queue, retry tasks) is still on `main` but not consumed by v1 user-facing flows. The new `send_dunning_email` task lives next to the v0 tasks in `notifications.py`; do NOT delete the v0 tasks (`send_failure_notification` is still called by quarantined polling code).

### Latest Tech Information

- **Django 6.0.x + django-fsm.** `@transition(field=status, source=[...], target=...)` accepts a list for `source`. The `post_transition` signal fires once per successful transition with `(sender, instance, name, source, target)`. Existing signal at `subscriber.py:87-99` already handles the audit write — Story 3.3's view-layer `manual_resolved` audit is COMPLEMENTARY, not a replacement.
- **DRF 3.17.x throttling.** `ScopedRateThrottle` requires both (a) `scope = "..."` on a subclass and (b) `"...": "10/min"` in `DEFAULT_THROTTLE_RATES`. The throttle key is `f"throttle_{scope}_{user.pk}"` for authenticated users. Cache backend: Django's default LocMem in dev / Redis in prod. Tests must `from django.core.cache import cache; cache.clear()` between throttle tests OR use unique users per test (the project's `auth_client` shares a user across tests in a class).
- **Celery 5.x.** `task.delay(args)` enqueues to the worker. **Tests do NOT use eager mode globally** — `CELERY_TASK_ALWAYS_EAGER` is NOT set in `safenet_backend/settings/*.py`. The test convention (see `backend/core/tests/test_tasks/test_notifications.py`) is to call the task **function** synchronously: `send_dunning_email(failure.id, "update_payment")`, NOT `send_dunning_email.delay(...)`. Production code enqueues via `.delay(...)` from the view; the worker picks it up.
- **Next.js 16 + TanStack Query v5.** `useMutation<TData, TError, TVariables>`. `mutate(variables, {onSuccess, onError})` for per-call callbacks (used in Story 3.3 to surface per-row toasts). `mutation.isPending` (NOT `isLoading` — v5 rename). `mutation.variables` exposes the in-flight call's variables — used to detect WHICH email type is currently sending in a multi-button row.
- **sonner 2.x.** `toast.error("msg", {duration: 6000})`. `richColors` prop on `<Toaster />` enables green/red palette. Duration `Infinity` requires manual dismiss.
- **axios `AxiosError`.** `err.response?.headers` is a plain object with lowercase keys per axios contract. `err.response?.data?.error` is the project's envelope path; `useSendEmail` wraps to a typed `SendEmailError`.
- **shadcn dropdown-menu.** v0+ uses Radix under the hood (verify in `dropdown-menu.tsx`); `<DropdownMenuItem onSelect={...}>` (NOT `onClick` — Radix-isms). `disabled` prop on `DropdownMenuItem` greys out the row but keeps it focusable.

### Project Structure Notes

**New files to create:**
- `backend/core/views/send_email.py` — both `send_email` and `mark_resolved` views (and the `_SendEmailThrottle` class)
- `backend/core/migrations/0016_extend_notification_email_type_choices.py` (latest on main is `0015_add_dpa_version_to_account.py`; bump if a sibling branch already took 0016)
- `backend/core/tests/test_api/test_send_email.py`
- `backend/core/tests/test_api/test_mark_resolved.py`
- `backend/core/tests/test_models/test_subscriber_fsm.py` (if the `test_models/` dir doesn't have FSM coverage yet — verify with `ls`)
- `frontend/src/hooks/useSendEmail.ts`
- `frontend/src/hooks/useMarkResolved.ts`
- `frontend/src/__tests__/useSendEmail.test.ts`

**Files to modify:**
- `backend/core/models/notification.py` — extend `EMAIL_TYPE_CHOICES`
- `backend/core/models/subscriber.py` — add `mark_resolved_manually()` FSM transition
- `backend/core/tasks/notifications.py` — add `bypass_engine_active` kwarg to `_passes_gates`; add `send_dunning_email` task + `CLIENT_MANUAL_EMAIL_TYPES` constant
- `backend/core/views/errors.py` — refactor throttled-message handling to per-scope map
- `backend/core/urls.py` — add `/send-email/` and `/mark-resolved/` routes
- `backend/safenet_backend/settings/base.py` — add `send_email: 10/min` to `DEFAULT_THROTTLE_RATES`
- `backend/core/tests/test_tasks/test_notifications.py` — extend with `send_dunning_email` tests (or create the file)
- `frontend/src/app/providers.tsx` — mount `<Toaster />`
- `frontend/src/components/dashboard/FailedPaymentsList.tsx` — rewrite `ActionButtons`, lift placeholder gate, plumb `row` through `PaymentRow`
- `frontend/src/hooks/useExcludeSubscriber.ts` — add `["failed-payments"]` to invalidation set
- `frontend/src/__tests__/FailedPaymentsList.test.tsx` — add 8 new tests + update placeholder-tooltip test

**Files NOT to modify:**
- `backend/core/views/dashboard.py` — `failed_payments_list` view is unchanged; `recommended_email_type` stays `None` until 3.5
- `backend/core/serializers/dashboard.py` — `FailedPaymentRowSerializer` is unchanged
- `backend/core/services/dpa.py` — `require_dpa_accepted` is reused as-is
- `backend/core/services/audit.py` — `write_audit_event` is reused as-is
- `backend/core/services/email.py` — email-builder functions are reused as-is; no new templates in this story
- `backend/core/views/actions.py` — `exclude_subscriber` is reused as-is
- `frontend/src/types/failed_payment.ts` — type unchanged; `RecommendedEmailType` covers all needed cases
- `frontend/src/hooks/useFailedPayments.ts` — query hook unchanged

**Files to delete:** none.

### References

- [Source: epics.md#Story 3.3 (v1):865-903] — ACs and FR coverage
- [Source: epics.md#FR53:183 / FR54:184 / FR55:185 / FR26:159 / FR27:160] — functional-requirement traceability
- [Source: sprint-change-proposal-2026-04-29.md] — v1 scope rationale; clients trigger every email by hand
- [Source: prd.md#FR16:496] — Four-status display vocabulary (Active / Recovered / Passive Churn / Fraud Flagged)
- [Source: prd.md#FR53] — Per-row dunning email trigger
- [Source: prd.md#FR55] — Manual mark-resolved → Recovered with audit note
- [Source: ux-design-specification.md#12.1:1040-1056] — One Primary CTA per row
- [Source: ux-design-specification.md UX-DR8 reframed] — Toast for per-row outcomes
- [Source: architecture.md#Naming Patterns:398-435] — snake_case + kebab-case URLs
- [Source: architecture.md#Format Patterns:489-510] — Response envelope contract
- [Source: architecture.md#Structure Patterns:439-477] — Django app organization (one route, one file)
- [Source: architecture.md#Process Patterns:570-590] — Error handling by layer + TanStack Query mutations
- [Source: 3-1-v1-dpa-acceptance-gate.md] — `require_dpa_accepted` contract; tooltip precedence
- [Source: 3-2-v1-current-month-failed-payments-dashboard.md] — `FailedPaymentsList` component, action button placeholders, `["failed-payments"]` cache key
- [Source: 4-3-final-notice-recovery-confirmation-emails.md] — `send_final_notice_email`, `send_recovery_confirmation_email`, NotificationLog partial unique constraint
- [Source: 4-4-opt-out-mechanism-notification-suppression.md] — `NotificationOptOut` model + per-(email, account_id) key
- [Source: backend/core/tasks/notifications.py:31-94] — `_passes_gates` 6-gate sequence
- [Source: backend/core/tasks/notifications.py:97-189] — `send_failure_notification` shape (mirror for `send_dunning_email`)
- [Source: backend/core/views/actions.py:109-148] — `exclude_subscriber` view (reused)
- [Source: backend/core/views/account.py:31-78] — `_ProfileThrottle` ScopedRateThrottle pattern (mirror for `_SendEmailThrottle`)
- [Source: backend/core/models/subscriber.py:32-58] — existing FSM transitions (pattern for `mark_resolved_manually`)
- [Source: frontend/src/hooks/useExcludeSubscriber.ts] — mutation hook shape (mirror for `useSendEmail` / `useMarkResolved`)
- [Source: frontend/src/components/common/UserMenu.tsx:50-77] — shadcn DropdownMenu composition example

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

- `makemigrations --dry-run` initially surfaced an unrelated `0017_alter_auditlog_actor` change — pre-existing drift from Story 4.4 (`ACTOR_SUBSCRIBER` choice added but never migrated). Per Sabri direction, captured as a sibling migration in this branch (Option 2) so post-merge `--dry-run` returns "No changes detected".
- `_SendEmailThrottle` first attempted as a `ScopedRateThrottle` subclass with `scope = "send_email"`. DRF's `ScopedRateThrottle.allow_request` overwrites `self.scope = getattr(view, "throttle_scope", None)` — which is `None` for `@api_view` function views — so the throttle silently no-opped. Switched to `SimpleRateThrottle` subclass with explicit `get_cache_key`. The `_ProfileThrottle` in `account.py` uses the same broken pattern (no test currently exercises it); flagged for reviewer follow-up.
- Pre-existing test `test_throttle_5_per_min_on_confirm` asserted "Too many password reset requests…" for the password-reset-confirm endpoint, which uses `scope="auth"`. The previous implementation used a hardcoded constant for ALL throttled responses, so the test passed by coincidence. The Story 3.3 refactor maps copy per-scope; the auth scope falls through to the new generic fallback. Updated the assertion to match — the user-facing surface (429 + `RATE_LIMITED` + `Retry-After`) is unchanged.
- Frontend tests for the per-row dropdown menuitem activation failed via `fireEvent.click` and `keyDown(Enter)` because Radix DropdownMenuItem uses an internal pointer-event lifecycle that jsdom doesn't drive. Replaced the dropdown-menu primitive with a passthrough mock in the test file so menuitem clicks deterministically dispatch `onSelect`.

### Completion Notes List

- All 7 ACs covered by automated tests (Tasks 8/9/10 backend, Tasks 16/17/18 frontend). Manual smoke (Task 19) deferred to reviewer per the explicit story note.
- Backend: 66 new tests added (17 send_email + 8 mark_resolved + 4 FSM unit + 8 send_dunning_email task + 1 password-reset-confirm assertion update). Full backend suite: 608 passed, 10 pre-existing failures (billing webhook env, dashboard tenant isolation, polling missed-cycle alert) unchanged from main.
- Frontend: 34 new tests added (7 useSendEmail + 27 FailedPaymentsList). Full frontend suite: 152 passed, 11 pre-existing failures (NavBar, BatchActionToolbar, ProfileComplete, ReviewQueuePage) unchanged from main.
- Sibling migration `0017_alter_auditlog_actor.py` added to capture the `ACTOR_SUBSCRIBER` choice introduced by Story 4.4. Choices-only AlterField — no DB schema change, no data migration.
- `_passes_gates` now accepts `bypass_engine_active=False` (default preserves v0 behavior; only `send_dunning_email` opts in). Existing 3 callers untouched. Tests confirm v0 path still suppresses with `engine_not_active` reason.
- Throttle scope `send_email` rate `10/min`. Per-user keying via `request.user.pk` (which equates to per-account in v1's single-membership model — flagged in the story Dev Notes as a future concern when Memberships ship).
- Toast positioning: `top-right` with `richColors`. Mounted Toaster in `providers.tsx` — also benefits the existing `toast.error/success` calls in `review-queue/page.tsx` and `activate/page.tsx` that were previously no-ops.
- Tooltip precedence kept tier > DPA, with the placeholder layer dropped. "Send recommended" gets a third tooltip layer ("No recommendation available yet") when `recommended_email_type === null` — orthogonal to gating per the UX spec.

### File List

**New files:**
- `backend/core/migrations/0016_extend_notification_email_type_choices.py`
- `backend/core/migrations/0017_alter_auditlog_actor.py` (drift cleanup, see Debug Log)
- `backend/core/views/send_email.py` (send_email + mark_resolved views, _SendEmailThrottle)
- `backend/core/tests/test_api/test_send_email.py`
- `backend/core/tests/test_api/test_mark_resolved.py`
- `backend/core/tests/test_models/test_subscriber_fsm.py`
- `frontend/src/hooks/useSendEmail.ts`
- `frontend/src/hooks/useMarkResolved.ts`
- `frontend/src/__tests__/useSendEmail.test.ts`

**Modified files:**
- `backend/core/models/notification.py` (extended EMAIL_TYPE_CHOICES)
- `backend/core/models/subscriber.py` (added mark_resolved_manually FSM transition)
- `backend/core/tasks/notifications.py` (bypass_engine_active kwarg + send_dunning_email task + CLIENT_MANUAL_EMAIL_TYPES constant)
- `backend/core/views/errors.py` (per-scope throttled-message map)
- `backend/core/urls.py` (added /send-email/ and /mark-resolved/ routes)
- `backend/safenet_backend/settings/base.py` (added send_email: 10/min throttle scope)
- `backend/core/tests/test_tasks/test_notifications.py` (TestSendDunningEmail class with 8 tests)
- `backend/core/tests/test_api/test_password_reset.py` (updated test_throttle_5_per_min_on_confirm assertion)
- `frontend/src/app/providers.tsx` (mounted &lt;Toaster richColors position="top-right" /&gt;)
- `frontend/src/components/dashboard/FailedPaymentsList.tsx` (rewrote ActionButtons, lifted placeholder gate, plumbed row through PaymentRow)
- `frontend/src/hooks/useExcludeSubscriber.ts` (added ["failed-payments"] invalidation)
- `frontend/src/__tests__/FailedPaymentsList.test.tsx` (added mocks for new hooks/sonner/dropdown; 16 new tests, updated 2 existing)
- `_bmad-output/3-3-v1-per-row-send-and-manual-resolve.md` (Status, File List, Change Log, Completion Notes)
- `_bmad-output/sprint-status.yaml` (status → in-progress, then will move to review)

### Change Log

- 2026-04-30: Story 3.3 v1 implemented — per-row send-email + manual-resolve + exclude wiring on the failed-payments dashboard.
- 2026-04-30: New POST /api/v1/subscribers/{id}/send-email/ endpoint with DPA → tier → validation → tenant → opt-out → exclusion → enqueue gate ordering. 10/min per-user throttle. 422 OPT_OUT and 422 EXCLUDED audit-blocking responses.
- 2026-04-30: New POST /api/v1/subscribers/{id}/mark-resolved/ endpoint backed by the new mark_resolved_manually FSM transition. Twin audit rows: `status_recovered` (engine, FSM signal) + `manual_resolved` (client, view).
- 2026-04-30: New send_dunning_email Celery task routes update_payment + retry_reminder to the failure-notice email builder and final_notice to the final-notice builder. Bypasses Gate 1 (engine_active); Gates 2–6 unchanged. notification_sent audits include `metadata.trigger="client_manual"`.
- 2026-04-30: Throttle error-message handling refactored from a single hardcoded constant to a per-scope map (`password_reset` + `send_email` mapped; other scopes fall through to a generic fallback). Updated test_throttle_5_per_min_on_confirm assertion accordingly (the password-reset-confirm endpoint uses `auth` scope, which now correctly returns the generic message).
- 2026-04-30: Frontend Toaster mounted in providers.tsx (top-right, richColors). Existing toast call sites in review-queue and activate pages are now functional.
- 2026-04-30: FailedPaymentsList ActionButtons rewritten — Send recommended (variant=default) + dropdown chevron + Mark resolved + Exclude. Per-row single-flight pending state. SendEmailError code branching maps RATE_LIMITED / OPT_OUT / EXCLUDED / DPA_REQUIRED to scoped toast messages and durations.
- 2026-04-30: Sibling migration 0017_alter_auditlog_actor captures pre-existing Story 4.4 drift (ACTOR_SUBSCRIBER choice). Choices-only — no DB schema change.
