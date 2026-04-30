# Story 4.3: Final Notice & Recovery Confirmation Emails

Status: needs-regeneration

> **POST-SIMPLIFICATION REGENERATION REQUIRED (2026-04-29).** This file is pre-simplification. The canonical post-simplification ACs live in `_bmad-output/epics.md` (Story 4.3, lines 1052–1077) — final notice is client-triggered (per-row or bulk with email type "Final notice"); recovery confirmation is polling-detected or manual-resolve-driven (no FSM auto-transition signal). Regenerate this file via SM workflow against the epics.md ACs before development resumes.

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mid-tier founder,
I want SafeNet to send a final notice before a subscriber graduates to Passive Churn, and a confirmation email when a payment is recovered,
So that every outcome is communicated clearly and the subscriber relationship is handled with dignity.

## Acceptance Criteria

1. **Given** a subscriber's failure is being scheduled for the **last permitted retry** (i.e. `failure.retry_count + 1 == decision.retry_cap`)
   **When** `schedule_retry()` queues that retry
   **Then** a `final_notice` email is dispatched (Celery task, `transaction.on_commit`) **before** the retry fires (FR24)
   **And** the email body says, in the selected tone, "This is our last attempt to process your payment. If unsuccessful, your subscription will be paused." (canonical content — exact phrasing modulated per tone, see "Tone Copy Reference")
   **And** the email is sent at most once per `(failure, email_type='final_notice')` — re-scheduling the same retry does not resend
   **And** if `retry_cap == 0` (no retries are permitted for that decline code) **no** final notice is sent — the subscriber is already on the path to `passive_churn` without a "last attempt" semantic

2. **Given** a `process_retry_result(failure, success=True)` call
   **When** the `_safe_transition(subscriber, "recover", account)` returns `True` (FSM transition `active → recovered` actually occurred)
   **Then** a `recovery_confirmation` email is dispatched (Celery task, `transaction.on_commit`) (FR25)
   **And** the email body is **two sentences maximum** ("All sorted — payment confirmed. Thanks for updating your details." voiced per tone — see "Tone Copy Reference")
   **And** the email contains **no CTA button** (the recovery has already happened — no action needed)
   **And** the email is sent at most once per `(failure, email_type='recovery_confirmation')`
   **And** if the `_safe_transition` returns `False` (block due to status drift, e.g. subscriber already in `passive_churn` from a parallel task) **no** confirmation is sent

3. **Given** the subscriber is already in `recovered` or `passive_churn` (i.e. not `active`) at the moment the engine attempts to schedule the final retry
   **When** `schedule_retry()` runs
   **Then** **no** final notice is dispatched — the FSM has already moved past the active state and the email would mislead the subscriber

4. **Given** either email type is dispatched
   **When** rendered
   **Then** the sender identity is the client's brand via the SafeNet shared domain — `"{company_name} via SafeNet" <notifications@{SAFENET_SENDING_DOMAIN}>` (FR28, identical to Story 4.1's `_build_from_field`)
   **And** an **opt-out link** is present and functional (placeholder URL until Story 4.4) (FR26)
   **And** the **selected tone preset** (`account.notification_tone`, default `professional`) is applied
   **And** the same gate-check sequence as Story 4.1 runs in order: `is_engine_active(account)` → `subscriber.email` non-blank → `subscriber.excluded_from_automation == False` → `NotificationOptOut` check → duplicate-`NotificationLog` check
   **And** **all** suppression and failure paths write a `NotificationLog` row (consistent with Story 4.1's review patch — every gate-fail path is queryable)

5. **Given** the recovery confirmation email path
   **When** `account.customer_update_url` is empty / unset
   **Then** the recovery confirmation **still sends** — it has no CTA URL, so it is **not** subject to the `SkipNotification` guard that `send_notification_email` (failure_notice) and the new `send_final_notice_email` enforce
   **And** the final notice path **DOES** raise `SkipNotification` when `customer_update_url` is empty (matches Story 4.1 contract — final notice has a CTA, recovery confirmation does not)

6. **Given** a Resend API error during dispatch
   **When** the task catches the exception
   **Then** it retries up to **3 times** with exponential backoff (matches `send_failure_notification` exactly — `@app.task(bind=True, max_retries=3, default_retry_delay=60)`)
   **And** if all retries fail, a `DeadLetterLog` row is written with `task_name="send_final_notice"` or `"send_recovery_confirmation"`, a `NotificationLog(status="failed")` row is written, and an audit event records `{action: "notification_failed", outcome: "failed", metadata: {email_type: <type>}}` (NFR-R3, NFR-R5)

7. **Given** the recovery confirmation timing requirement (FR25 + epic-spec line 859: "within 5 minutes of the successful retry")
   **When** the confirmation is dispatched via `transaction.on_commit(lambda: send_recovery_confirmation.delay(failure_id))`
   **Then** the dispatch round-trip is "Stripe confirms success → DB commit → Celery `.delay()` → worker picks up → Resend send" — typical wall-clock latency well under 5 minutes given the existing 1-minute Celery default retry delay; **no explicit ETA / countdown is required**
   **And** there is a documented `# 5-minute SLA` comment at the call site so future changes do not add a `countdown=` arg by accident

## Tasks / Subtasks

- [x] **Task 1: Backend — Tone copy for the two new email types** (AC: 1, 2, 4)
  - [x] 1.1 In `backend/core/services/email_templates.py`, add two new frozen dataclasses **alongside** the existing `ToneTemplate` (do **not** widen `ToneTemplate` — the shapes differ and merging would produce dead optional fields):
    ```python
    @dataclass(frozen=True)
    class FinalNoticeTemplate:
        subject: Callable[[str], str]            # company → subject
        greeting: str                            # may be empty
        body_paragraphs: Callable[[str], list[str]]   # company → paragraphs (raw)
        cta_label: str
        footer: Callable[[str], str]

    @dataclass(frozen=True)
    class RecoveryConfirmationTemplate:
        subject: Callable[[str], str]
        greeting: str
        body_paragraphs: Callable[[str], list[str]]   # ≤ 2 strings — cap by construction
        footer: Callable[[str], str]
        # NO cta_label field — confirmation has no button
    ```
  - [x] 1.2 Add module-level dicts:
    ```python
    FINAL_NOTICE_TEMPLATES: dict[str, FinalNoticeTemplate] = {
        TONE_PROFESSIONAL: _FINAL_NOTICE_PROFESSIONAL,
        TONE_FRIENDLY:     _FINAL_NOTICE_FRIENDLY,
        TONE_MINIMAL:      _FINAL_NOTICE_MINIMAL,
    }
    RECOVERY_CONFIRMATION_TEMPLATES: dict[str, RecoveryConfirmationTemplate] = {...}
    ```
  - [x] 1.3 Add accessor helpers next to the existing `get_template`:
    ```python
    def get_final_notice_template(tone: str | None) -> FinalNoticeTemplate: ...
    def get_recovery_confirmation_template(tone: str | None) -> RecoveryConfirmationTemplate: ...
    ```
    Both fall back to `DEFAULT_TONE` exactly like `get_template` does (line 98-100 of `email_templates.py`).
  - [x] 1.4 Copy is fully specified in "Tone Copy Reference" below — implement **verbatim**. All copy is GDPR transactional. Zero marketing language. Recovery confirmation MUST stay ≤ 2 body paragraphs in **every** tone (cap by construction — `body_paragraphs` returns a list literal of length 2 in Professional/Friendly and length 1 in Minimal).
  - [x] 1.5 Module docstring already states the GDPR-transactional-only constraint (line 4 of current `email_templates.py`); leave it untouched.

- [x] **Task 2: Backend — Two new email-builder functions in `email.py`** (AC: 1, 2, 4, 5)
  - [x] 2.1 In `backend/core/services/email.py`, add `send_final_notice_email(subscriber, failure, account) -> str` modeled on `send_notification_email` (lines 132-196):
    - Same `_ensure_configured()` call up front
    - Same `tone = account.notification_tone or DEFAULT_TONE` resolution
    - Same `customer_update_url` guard — **MUST** raise `SkipNotification` when missing (final notice carries a CTA, parity with failure_notice)
    - Same `_build_from_field`, recipient strip+lowercase, `SkipNotification` on blank email
    - Build subject via a new helper `_build_final_notice_subject(company_name, tone)` that wraps `get_final_notice_template(tone).subject(safe_company)` and runs the result through `_sanitize_header(...)` (CRLF defense — non-negotiable, 4.1 review item)
    - Build HTML via a new helper `_build_final_notice_html_body(company_name, portal_url, opt_out_url, tone)` that mirrors `_build_html_body` exactly **except**:
      - Skips the `DECLINE_CODE_LABELS` lookup (final notice copy is decline-code-agnostic per spec)
      - Uses `get_final_notice_template(tone)` for greeting/paragraphs/cta/footer
      - **Reuses the same outer table chrome / colors / fonts** — copy the entire `<!DOCTYPE html>...</html>` shell from `_build_html_body` lines 105-129 verbatim. **Do NOT** introduce a second visual style — UX line 767-771: "Sender is Marc's brand — Sophie has no awareness of SafeNet. Recovery confirmation is brief — two sentences maximum." consistency wins.
      - Apply `html.escape()` per paragraph and on `cta_label`/`footer_text` exactly as the existing function does (lines 90-103). The 4.2 review's open footer-double-escape patch (`Patch — Footer text is double HTML-escaped`) lives at line 103 — **fix it for all three email types in this story**: pass raw `company_name` once, escape once at the f-string boundary. Do NOT regress.
      - Apply the body-paragraph defense-in-depth `html.escape(p)` per paragraph (already in 4.2 line 91) — keep it, do not remove.
  - [x] 2.2 Add `send_recovery_confirmation_email(subscriber, failure, account) -> str` similar but:
    - **No** `customer_update_url` requirement — the body has no CTA
    - **No** CTA button in the rendered HTML — the helper `_build_recovery_confirmation_html_body(company_name, opt_out_url, tone)` outputs the brand header + greeting + 1-2 escaped paragraphs + footer + opt-out link, with **no `<a>` button block** (skip lines 115-121 of the existing helper — drop the entire `<table cellpadding=...><tr><td style="background:#2563eb...">` block)
    - Subject via `_build_recovery_confirmation_subject(company_name, tone)`
  - [x] 2.3 **Refactor opportunity (do this once, cleanly):** the outer `<!DOCTYPE html>`/`<head>`/`<body>`/outer `<table>` chrome appears in three places after this story. Extract a small private helper `_render_email_shell(brand_header_company: str, inner_html: str) -> str` that takes the already-escaped company name (for the `<h2>`) and pre-rendered inner HTML (greeting+paragraphs+CTA+footer+opt-out) and returns the full document. Update `_build_html_body` (existing failure_notice) to use this shell as well. Keep this refactor scoped — do not rename existing helpers, do not change the rendered HTML output (snapshot equivalence — extend the existing 4.1 escape tests to assert the shell passes through unchanged).
  - [x] 2.4 Logging parity: each new builder logs `"[send_final_notice_email] Sent to=%s resend_id=%s failure_id=%s"` and the equivalent for confirmation. Reuse the same `logger = logging.getLogger(__name__)` instance.

- [x] **Task 3: Backend — Two new Celery tasks in `notifications.py`** (AC: 1, 2, 4, 5, 6)
  - [x] 3.1 In `backend/core/tasks/notifications.py`, add `send_final_notice(self, failure_id: int)` modeled on `send_failure_notification` (lines 24-144) **exactly**:
    - Same decorator: `@app.task(bind=True, max_retries=3, default_retry_delay=60)`
    - Same `failure = SubscriberFailure.objects.select_related(...).get(id=failure_id)` lookup with `DoesNotExist` → log + return
    - Same gate sequence in the same order: `is_engine_active(account)` → email non-blank → `excluded_from_automation` → `NotificationOptOut.objects.filter(subscriber_email__iexact=..., account=account).exists()` → duplicate `NotificationLog` check (`email_type="final_notice"`, `status="sent"`)
    - On success: `NotificationLog(email_type="final_notice", status="sent", resend_message_id=msg_id)` + audit `notification_sent` with `metadata={"email_type": "final_notice", "decline_code": failure.decline_code, "resend_message_id": msg_id}`
    - `SkipNotification` → `_log_suppression(..., reason="skip_permanent")` — already case-handled, just thread the new email_type through (see 3.3)
    - `EmailConfigurationError` → `_record_failure(...)`
    - All other exceptions → `self.retry(exc=exc)` until `max_retries`, then `_record_failure(...)`
  - [x] 3.2 Add `send_recovery_confirmation(self, failure_id: int)` with the same shape, BUT:
    - The `is_engine_active(account)` gate is **kept** (parity — Free-tier subscribers should not receive any branded SafeNet email)
    - The `excluded_from_automation` gate is **kept** (a manually-excluded subscriber should not get a confirmation either — consistent with the failure_notice rule)
    - The opt-out + duplicate gates are **kept**, with `email_type="recovery_confirmation"`
    - `SkipNotification` should **never** be raised in practice (no `customer_update_url` guard in the recovery confirmation builder), but the task still catches it for defensive parity
  - [x] 3.3 Generalize `_log_suppression` and `_record_failure` to accept an `email_type` argument (currently hard-codes `"failure_notice"` at lines 153 and 167-168 of `notifications.py`):
    ```python
    def _log_suppression(subscriber, failure, account, *, reason: str, email_type: str): ...
    def _record_failure(subscriber, failure, account, exc, *, email_type: str): ...
    ```
    Update all existing callers in `send_failure_notification` to pass `email_type="failure_notice"`. Update task names threaded into `DeadLetterLog.task_name` so the new tasks write `"send_final_notice"` and `"send_recovery_confirmation"` accordingly (currently hard-coded at line 184 of `notifications.py`).
  - [x] 3.4 **Test the generalization** before adding new tests — re-run `core/tests/test_tasks/test_notifications.py` (10 tests in `TestSendFailureNotification`); they must still pass with no signature errors.

- [x] **Task 4: Backend — Trigger final notice from `schedule_retry()`** (AC: 1, 3)
  - [x] 4.1 In `backend/core/services/recovery.py` `schedule_retry()` (lines 140-198), inside the **non-cap branch** (line 174 onwards, after `failure.next_retry_at = next_retry_at; failure.save(update_fields=["next_retry_at"])` at lines 182-183), add:
    ```python
    # Final notice: this dispatch fires when the retry being scheduled is the
    # LAST one permitted by the rule. retry_count is the count BEFORE this
    # retry executes; the upcoming retry is retry_count + 1.
    is_last_retry = (failure.retry_count + 1) == decision.retry_cap
    if is_last_retry and decision.retry_cap > 0:
        from django.db import transaction
        from core.tasks.notifications import send_final_notice
        failure_id = failure.id
        transaction.on_commit(
            lambda fid=failure_id: send_final_notice.delay(fid)
        )
    ```
    — `decision.retry_cap > 0` is redundant given the cap-exhausted branch above, but it documents the invariant defensively.
  - [x] 4.2 The dispatch fires **after** the `failure.save()` so the `failure_id` is durable, and **inside** `transaction.on_commit` so a rollback (e.g. concurrent `select_for_update` collision) doesn't enqueue an orphan task. Mirror the polling.py pattern at lines 132-136 verbatim.
  - [x] 4.3 The audit `retry_scheduled` event at lines 185-198 is **unchanged**. Add a new audit event right after the dispatch:
    ```python
    if is_last_retry and decision.retry_cap > 0:
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="final_notice_dispatched",
            outcome="success",
            metadata={
                "decline_code": decision.decline_code,
                "retry_number": failure.retry_count + 1,
                "retry_cap": decision.retry_cap,
                "failure_id": str(failure.id),
            },
            account=account,
        )
    ```
    Note: the audit row records the **dispatch** (the delivery success/failure is recorded separately by the notification task). This separation matches the failure_notice pattern.
  - [x] 4.4 **AC 3 — status guard:** `_safe_transition(..., "recover", ...)` and `_safe_transition(..., "mark_passive_churn", ...)` already gate on `subscriber.status == STATUS_ACTIVE` upstream. `schedule_retry` does not need an additional guard — but if `subscriber.status != STATUS_ACTIVE` at this point, `execute_retry` would already short-circuit (line 52 of `retry.py`). Add a defensive log line: `if subscriber.status != STATUS_ACTIVE: logger.info("[schedule_retry] Skipping final notice — subscriber %s is %s", subscriber.id, subscriber.status); return`. Place this guard **before** the dispatch block in 4.1.

- [x] **Task 5: Backend — Trigger recovery confirmation from `process_retry_result()`** (AC: 2, 7)
  - [x] 5.1 In `backend/core/services/recovery.py` `process_retry_result()` (lines 201-251), inside the `if success:` branch (line 216), modify:
    ```python
    if success:
        failure.next_retry_at = None
        failure.save(update_fields=["retry_count", "last_retry_at", "next_retry_at"])

        transitioned = False
        if subscriber.status == STATUS_ACTIVE:
            transitioned = _safe_transition(subscriber, "recover", account)

        write_audit_event(...)  # existing retry_succeeded — unchanged

        # Recovery confirmation: dispatch only if the FSM transition actually
        # occurred. If the subscriber was already non-ACTIVE (status drift,
        # parallel task, manual operator action) the transition returns False
        # and we do not send a confirmation — see AC 2.
        if transitioned:
            from django.db import transaction
            from core.tasks.notifications import send_recovery_confirmation
            failure_id = failure.id
            # 5-minute SLA per FR25; no countdown= needed — Celery worker
            # picks up immediately and Resend send completes well under 5min.
            transaction.on_commit(
                lambda fid=failure_id: send_recovery_confirmation.delay(fid)
            )
    ```
    Capture the `_safe_transition` return value (it already returns `True`/`False` per line 33-61) and gate the dispatch on it. Today the return value is discarded.
  - [x] 5.2 No new audit event needed at the recovery callsite — the existing `retry_succeeded` audit + the FSM `post_transition` signal handler in `models/subscriber.py` lines 87-99 already record the transition. The notification task itself writes the `notification_sent`/`notification_suppressed`/`notification_failed` audit row.
  - [x] 5.3 **AC 2 — TransitionNotAllowed parity:** `_safe_transition` already swallows `TransitionNotAllowed` and writes a `transition_blocked_recover` audit event (line 50-60 of recovery.py). When that happens it returns `False`, so our `if transitioned:` gate suppresses the confirmation. No additional code needed.

- [x] **Task 6: Backend — Migration: add `(failure, email_type)` partial unique constraint** (AC: 1, 2)
  - [x] 6.1 Story 4.1 deferred this exact issue (review patch at line 105 of 4-1 spec — TOCTOU on the duplicate-`NotificationLog` check). With **three** email types now writing to the same table, the race window is wider and the operational cost (duplicate "your subscription will be paused" emails) is high. Land the constraint in this story.
  - [x] 6.2 Add to `backend/core/models/notification.py` `NotificationLog.Meta.constraints`:
    ```python
    models.UniqueConstraint(
        fields=["failure", "email_type"],
        condition=models.Q(status="sent"),
        name="unique_sent_notification_per_failure_email_type",
    )
    ```
    Partial unique on `status="sent"` so multiple `suppressed` / `failed` rows remain valid (they already are — gate-fail rows can repeat across polling cycles per 4.1 design).
  - [x] 6.3 Generate migration: `poetry run python manage.py makemigrations core` → expect `0014_notification_unique_sent_per_failure.py`. Verify with `manage.py sqlmigrate core 0014` that PostgreSQL gets a `CREATE UNIQUE INDEX ... WHERE status = 'sent'`.
  - [x] 6.4 Wrap the `NotificationLog.objects.create(..., status="sent", ...)` calls in all three task functions with `try: ... except IntegrityError: _log_suppression(..., reason="duplicate_race")` — the gate check at line 77-84 of `notifications.py` is now a fast-path; the constraint is the source of truth. Match the existing pattern: log the duplicate-race as a suppression so the audit trail stays consistent.

- [x] **Task 7: Backend — Tests for the new email builders** (AC: 1, 2, 4)
  - [x] 7.1 Extend `backend/core/tests/test_services/test_email.py` (existing 4.1+4.2 file). For each of the three tones (parametrize), add:
    - `test_final_notice_subject_uses_<tone>` — assert key phrase from the canonical subject appears
    - `test_final_notice_body_contains_canonical_message` — assert the rendered body contains the per-tone phrasing of "this is our last attempt … subscription will be paused" (substring assertion, not exact match — leaves room for safe minor copy edits)
    - `test_final_notice_html_escapes_company_name` — pass `company_name="<script>alert(1)</script>"`, assert `&lt;script&gt;` substring appears in the **entire** rendered body **including the footer** (4.2 review patch — the existing failure_notice tests miss this; cover it now for both new email types)
    - `test_final_notice_skips_without_customer_update_url` — `account.customer_update_url=""`; expect `SkipNotification`
    - `test_recovery_confirmation_subject_uses_<tone>`
    - `test_recovery_confirmation_body_max_two_paragraphs` — count `<p>` blocks inside the body section (excluding header `<h2>` and footer `<p style="color:#999...">`); assert `<= 2`. Use the same regex/parser approach as the existing `test_body_minimal_has_max_two_paragraphs` in test_email.py.
    - `test_recovery_confirmation_no_cta_button` — assert the rendered HTML does **NOT** contain `style="background:#2563eb"` (the CTA button color from `_build_html_body` line 116) and does NOT contain a `<a href=` pointing at a portal URL
    - `test_recovery_confirmation_sends_without_customer_update_url` — `account.customer_update_url=""`; `send_recovery_confirmation_email` must succeed (mocked Resend), no `SkipNotification`
    - `test_recovery_confirmation_html_escapes_company_name` — same XSS guard as above
    - `test_email_shell_unchanged_after_refactor` — render a failure_notice with a known fixed input, assert the existing 4.1+4.2 snapshot still matches (use `assert "expected substring" in html_body` not full-string compare; the 4.2 review showed full-string compares are brittle)
  - [x] 7.2 Re-run the existing 4.2 escape parametrization across **all three** email types (Resend SDK mocked). The `_HEADER_INJECTION_CHARS` regex already covers Unicode line separators (4.2 patch). The footer-double-escape fix from Task 2 must be verified by adding a footer-XSS assertion to the existing test fixture.

- [x] **Task 8: Backend — Tests for the trigger logic in recovery.py** (AC: 1, 2, 3)
  - [x] 8.1 Extend `backend/core/tests/test_services/test_recovery.py` (existing 3.2 file). Add a new class `TestFinalNoticeDispatch`:
    - `test_final_notice_dispatched_on_last_retry` — `failure.retry_count=2`, `decision.retry_cap=3`; mock `transaction.on_commit` (or use Django's `CaptureQueriesContext` / pytest-django `mocker.patch("core.tasks.notifications.send_final_notice.delay")`); call `schedule_retry(failure, decision)`; assert `.delay(failure.id)` was called exactly once.
    - `test_final_notice_not_dispatched_when_not_last_retry` — `retry_count=0`, `retry_cap=3`; assert `.delay` was NOT called.
    - `test_final_notice_not_dispatched_when_retry_cap_zero` — `retry_count=0`, `retry_cap=0`; the cap-exhausted branch fires; assert `.delay` was NOT called and `mark_passive_churn` was attempted.
    - `test_final_notice_not_dispatched_when_subscriber_inactive` — pre-set `subscriber.status=STATUS_RECOVERED` (use direct `Subscriber.objects.filter(...).update(status=...)` to bypass FSM); `retry_count=2`, `retry_cap=3`; assert `.delay` was NOT called.
    - `test_final_notice_dispatched_after_commit` — verify the dispatch is wrapped in `transaction.on_commit` and does NOT fire if the surrounding atomic block rolls back. Use `transaction.atomic()` + raise to exercise the rollback path. Match the polling-test pattern used in 4.1.
    - `test_final_notice_dispatched_when_retry_cap_one` — boundary case: `retry_count=0`, `retry_cap=1`; the **first** retry IS the last retry; assert `.delay` IS called.
    - `test_final_notice_dispatch_writes_audit_event` — assert `final_notice_dispatched` audit row is created with the right metadata.
  - [x] 8.2 Add a new class `TestRecoveryConfirmationDispatch`:
    - `test_recovery_confirmation_dispatched_on_successful_recover` — call `process_retry_result(failure, success=True)`; subscriber status starts ACTIVE; mock `send_recovery_confirmation.delay`; assert called once after commit.
    - `test_recovery_confirmation_NOT_dispatched_on_failed_retry` — `process_retry_result(failure, success=False)`; assert `.delay` NOT called.
    - `test_recovery_confirmation_NOT_dispatched_when_already_recovered` — pre-set `subscriber.status=STATUS_RECOVERED` via direct `.update()`; `process_retry_result(failure, success=True)`; the `if subscriber.status == STATUS_ACTIVE` guard at line 220 short-circuits the transition; assert `.delay` NOT called.
    - `test_recovery_confirmation_NOT_dispatched_when_transition_blocked` — patch `_safe_transition` to return `False`; assert `.delay` NOT called.
    - `test_recovery_confirmation_idempotent_per_failure` — call `process_retry_result` twice for the same failure; the second call's transition returns `False` (subscriber is already RECOVERED); assert `.delay` was called exactly once (at the first call).

- [x] **Task 9: Backend — Tests for the two new Celery tasks** (AC: 4, 5, 6)
  - [x] 9.1 Extend `backend/core/tests/test_tasks/test_notifications.py`. Mirror the 10-test structure of `TestSendFailureNotification` for both new tasks:
    - `TestSendFinalNotice` — success_path, free_tier_suppressed, no_dpa_suppressed, no_email_skipped, excluded_subscriber_suppressed, opt_out_suppressed, duplicate_suppressed, retry_on_api_error, dead_letter_on_exhausted_retries, nonexistent_failure_handled, **+ skip_when_no_customer_update_url** (asserts `SkipNotification` produces a `_log_suppression(reason="skip_permanent")` row, mirroring the 4.1 patch at line 121-122 of `notifications.py`)
    - `TestSendRecoveryConfirmation` — success_path, free_tier_suppressed, no_dpa_suppressed, no_email_skipped, excluded_subscriber_suppressed, opt_out_suppressed, duplicate_suppressed, retry_on_api_error, dead_letter_on_exhausted_retries, nonexistent_failure_handled, **+ sends_without_customer_update_url** (asserts the task succeeds with `account.customer_update_url=""`, no `SkipNotification` raised)
  - [x] 9.2 The `mid_account` fixture at lines 25-39 of the existing file provides `tier=mid + dpa_accepted_at + engine_mode + company_name + StripeConnection`. Reuse it directly. Do **not** duplicate the fixture into the new test classes — extend at module scope.
  - [x] 9.3 Patch target for each test class is `core.tasks.notifications.send_final_notice_email` / `send_recovery_confirmation_email` — same pattern as the existing `@patch("core.tasks.notifications.send_notification_email")` decorator.
  - [x] 9.4 Add a regression assertion that `_log_suppression(...)` and `_record_failure(...)` accept the new `email_type=` kwarg (Task 3.3) — at least one test per new class asserts `NotificationLog.objects.filter(email_type="final_notice", status="suppressed").exists()` or `email_type="recovery_confirmation"`.

- [x] **Task 10: Backend — Migration test for the partial unique constraint** (AC: 1, 2, Task 6)
  - [x] 10.1 Add `backend/core/tests/test_models/test_notification.py::test_unique_sent_per_failure_constraint` — create a `NotificationLog(status="sent", email_type="final_notice", failure=F)`; attempt to create a second one with the same `(failure, email_type)`; expect `IntegrityError`. Then create a third with `status="suppressed"` and the same `(failure, email_type)`; expect success (the partial constraint allows it).
  - [x] 10.2 Add `test_unique_constraint_does_not_apply_across_email_types` — `NotificationLog(status="sent", email_type="failure_notice")` + `(status="sent", email_type="final_notice")` for the same failure — both succeed.

## Dev Notes

### Architecture Compliance

- **Trigger sites are explicit, not signal-based.** Final notice fires inline in `schedule_retry()` (recovery.py); recovery confirmation fires inline in `process_retry_result()` after a verified `_safe_transition` success. We do **not** add a new `post_transition` listener — those run before the surrounding transaction commits and would race with the `transaction.on_commit` dispatch.
- **`transaction.on_commit` mandatory.** Both new dispatches are wrapped in `transaction.on_commit(lambda fid=...: ...delay(fid))` to avoid orphan tasks if the outer atomic block rolls back. This pattern was added to polling.py during the Story 4.1 review batch (lines 132-136) — replicate it byte-for-byte.
- **`_safe_transition` return value is now load-bearing.** Today its bool return is discarded everywhere except in `execute_recovery_action`. Story 4.3 introduces the first read-side use (Task 5.1) — this is intentional, no refactor of other call sites is in scope.
- **No new public API endpoints.** This story is engine-side / Celery-side / template only. The Settings UI for tone (Story 4.2) already covers the user-visible surface; the live preview endpoint (`/api/v1/account/notification-preview/`) is **failure-notice-only by design** (per 4.2 spec — the preview is a sales surface, not a complete email-type browser). Do **not** widen it. **Do not** add `?email_type=final_notice|recovery_confirmation` to the preview endpoint.
- **Tone copy is the single source of truth.** Both new email types route their copy through `email_templates.py`. The frontend never reimplements anything from this story.
- **Sanitization carries forward (4.1 + 4.2 patches).** `_sanitize_header` at email.py:46 already strips Unicode line separators (4.2 patch). All HTML interpolation uses `html.escape()`. Footer double-escape (4.2 open patch) gets fixed in this story for all three email types — Task 2.1 explicitly requires it. The body-paragraph-per-string `html.escape(p)` defense-in-depth (4.2 patch) stays.
- **Account.customer_update_url is still a follow-up.** Both Stories 4.1 and 4.2 noted this field doesn't exist yet — `getattr(account, "customer_update_url", "") or ""` returns `""` and `send_notification_email` raises `SkipNotification`. Story 4.3 inherits this exact contract for `send_final_notice_email`. **Do not** add the field in this story — it belongs in the Stripe Connect onboarding follow-up (Story 2.1 territory). `send_recovery_confirmation_email` does NOT need the field (no CTA).
- **Engine-side, not retry-side, hook for final notice.** The decision to fire the email lives at scheduling time (`schedule_retry`), NOT at execution time (`execute_retry`). This is non-negotiable: the spec says "before the retry fires", and scheduling-time dispatch gives the worker minutes-to-hours of runway depending on `payday_aware` rules.

### Existing Code to Reuse (DO NOT reinvent)

| What | Where | Usage |
|------|-------|-------|
| `_build_from_field` | `backend/core/services/email.py:53` | Branded `From` — DO NOT inline the format string twice. |
| `_sanitize_header` | `backend/core/services/email.py:46` | CRLF/Unicode line separator strip. |
| `_HEADER_INJECTION_CHARS` regex | `backend/core/services/email.py:26` | Already covers `\r\n\u2028\u2029\u0085"<>` (4.2 patch). |
| `_ensure_configured` | `backend/core/services/email.py:37` | Just-in-time Resend API-key check. |
| `SkipNotification` / `EmailConfigurationError` | `backend/core/services/email.py:29-34` | Exception types for the task layer. |
| `get_template` accessor pattern | `backend/core/services/email_templates.py:98-100` | Copy this fallback pattern for the two new accessors. |
| `ToneTemplate` shape (NOT the dataclass itself) | `backend/core/services/email_templates.py:19-26` | Pattern to follow: frozen dataclass, callables for variable copy, plain strings for fixed copy. |
| `send_failure_notification` task structure | `backend/core/tasks/notifications.py:24-144` | The 5-gate sequence + retry/DLL/audit pattern. Copy verbatim. |
| `_log_suppression`, `_record_failure` | `backend/core/tasks/notifications.py:147-215` | Generalize, do NOT duplicate. |
| `transaction.on_commit` dispatch pattern | `backend/core/tasks/polling.py:132-136` | The lambda-with-default-arg trick to capture `failure_id`. |
| `_safe_transition` return value | `backend/core/services/recovery.py:33-61` | Already returns bool; consume it (Task 5.1). |
| `schedule_retry` | `backend/core/services/recovery.py:140-198` | Trigger site for final notice — modify in place. |
| `process_retry_result` | `backend/core/services/recovery.py:201-251` | Trigger site for recovery confirmation. |
| `NotificationLog` model | `backend/core/models/notification.py:18-39` | `email_type` field already supports `final_notice` and `recovery_confirmation` (lines 5-9). No model change needed beyond the new constraint. |
| `mid_account` fixture | `backend/core/tests/test_tasks/test_notifications.py:25-39` | Reuse for both new test classes. |
| `_make_decision` test helper | `backend/core/tests/test_services/test_recovery.py:21-30` | Reuse for the new TestFinalNoticeDispatch class. |
| Existing `test_body_minimal_has_max_two_paragraphs` | `backend/core/tests/test_services/test_email.py` | Reference for the recovery-confirmation max-two-paragraphs test. |

### What NOT to Do

- Do **NOT** add a new `Account.customer_update_url` field. That migration belongs in a separate Story 2.1 follow-up. Inherit the `getattr(...)` + `SkipNotification` contract from Story 4.1.
- Do **NOT** widen `ToneTemplate` with new fields — the field shapes differ across email types (final notice has CTA, recovery confirmation does not, failure notice has card_expired branch). Use distinct dataclasses.
- Do **NOT** introduce Django templates, Jinja, or `render_to_string`. Inline HTML strings continue per 4.1's MVP decision (4.1 spec line 145).
- Do **NOT** add a CTA to the recovery confirmation email. UX line 771 is explicit: "Recovery confirmation is brief — two sentences maximum." No CTA.
- Do **NOT** add an explicit Celery `countdown=` to the recovery confirmation dispatch. The 5-minute SLA is met by the default Celery worker pickup latency. A `countdown` would slow it down and add a foot-gun for future debugging.
- Do **NOT** reuse `send_failure_notification` for either new email type. The gate sequence is shared, but the email-type identity, template lookup, and audit-event metadata diverge — keep three discrete tasks for clarity.
- Do **NOT** trigger the recovery confirmation from a `post_transition` signal handler. Signals fire **before** the surrounding transaction commits; combined with `transaction.on_commit` in the handler, there's a race where the email enqueues against an uncommitted state. The inline call in `process_retry_result()` is correct.
- Do **NOT** trigger the final notice from `execute_retry` (the retry-execution Celery task). The spec says **before** the retry fires; the dispatch must happen at scheduling time.
- Do **NOT** widen the `notification_preview` endpoint to support `?email_type=final_notice` or `?email_type=recovery_confirmation`. Story 4.2 deliberately scoped the preview to failure_notice; expanding it is a Story 4.4+ scope decision and would require additional UX work.
- Do **NOT** swallow the `_safe_transition` return value in `process_retry_result()`. Today it's discarded; Task 5.1 makes it a guard for the dispatch.
- Do **NOT** send a recovery confirmation per failure if a subscriber has multiple failures. The `(failure_id, email_type='recovery_confirmation', status='sent')` partial unique constraint (Task 6) makes this impossible — the **specific** failure that succeeded its retry is the one that triggers; only one transition `active → recovered` is possible per subscriber per recovery cycle (FSM enforces it).
- Do **NOT** modify scanner.py or trial_expiration.py. Final notice and recovery confirmation are real-time events — not retroactive, not scheduled.
- Do **NOT** add frontend changes. This story is engine + email-template only. Story 4.4 will add the opt-out endpoint (UI) and Story 4.5 the password reset.

### Tone Copy Reference (canonical — implementation source)

These are the only authorized copies. Any deviation requires updating this story.

#### Final Notice — `final_notice`

| Tone | Element | Copy |
|------|---------|------|
| **Professional** | Subject | `Final attempt to process your payment — {company}` |
|  | Greeting | `Hello,` |
|  | Body ¶1 | `This is our final attempt to process your payment to {company}.` |
|  | Body ¶2 | `If it does not succeed, your subscription will be paused. You can avoid this by updating your payment details now:` |
|  | CTA label | `Update Payment Details` |
|  | Footer | `This email was sent on behalf of {company} by SafeNet.` |
| **Friendly** | Subject | `Heads up — last try on your {company} payment` |
|  | Greeting | `Hi there,` |
|  | Body ¶1 | `Just a heads-up — this is our last try at processing your payment to {company}.` |
|  | Body ¶2 | `If it doesn't go through, your subscription will be paused. You can sort this out right now by updating your details:` |
|  | CTA label | `Update your details` |
|  | Footer | `Sent by {company} via SafeNet.` |
| **Minimal** | Subject | `Final attempt — {company}` |
|  | Greeting | *(empty)* |
|  | Body ¶1 | `Final attempt to process your payment to {company}.` |
|  | Body ¶2 | `If unsuccessful, your subscription will be paused. Update your card to keep it active:` |
|  | CTA label | `Update card` |
|  | Footer | `{company} via SafeNet.` |

> **Canonical-message rule:** every tone's body MUST contain (in voice) the substance of "this is our last attempt; if unsuccessful, your subscription will be paused" (FR24, epic spec line 852). Tests assert this by substring (e.g. `"last attempt"` or `"final attempt"` AND `"paused"`).

#### Recovery Confirmation — `recovery_confirmation`

| Tone | Element | Copy |
|------|---------|------|
| **Professional** | Subject | `Payment confirmed — {company}` |
|  | Greeting | `Hello,` |
|  | Body ¶1 | `Your payment to {company} has been confirmed.` |
|  | Body ¶2 | `Thank you for updating your details.` |
|  | Footer | `This email was sent on behalf of {company} by SafeNet.` |
| **Friendly** | Subject | `All sorted — payment confirmed for {company}` |
|  | Greeting | `Hi there,` |
|  | Body ¶1 | `All sorted — your payment to {company} has been confirmed.` |
|  | Body ¶2 | `Thanks for updating your details!` |
|  | Footer | `Sent by {company} via SafeNet.` |
| **Minimal** | Subject | `Payment confirmed — {company}` |
|  | Greeting | *(empty)* |
|  | Body ¶1 | `Payment to {company} confirmed.` |
|  | Footer | `{company} via SafeNet.` |

> **Two-sentences-max rule (UX line 771):** Professional and Friendly each return exactly **2** body paragraphs (2 sentences). Minimal returns exactly **1**. The cap is enforced **by construction** — `body_paragraphs` returns a list literal of fixed length per tone. Tests count `<p>` blocks inside the body section.

### API Contracts

This story does **not** introduce or modify any HTTP API endpoints. All new behavior is engine-side / Celery-task-side. The Story 4.2 endpoints (`/api/v1/account/notification-tone/`, `/api/v1/account/notification-preview/`, `/api/v1/account/me/`) are unchanged.

### Tenant Isolation

- `NotificationLog` already inherits from `TenantScopedModel` — every new row in this story carries the `account` FK.
- The duplicate-`NotificationLog` gate query at notifications.py:77-83 already filters by `account=account`. Both new tasks reuse this exact filter.
- The new partial unique constraint (Task 6) is on `(failure, email_type)` — `failure` already implicitly scopes to a single account via `failure.account_id`. No cross-tenant collision is possible.
- `NotificationOptOut` opt-out checks (notifications.py:69-72) are scoped per `(subscriber_email, account)` — both new tasks honour this exact lookup. A subscriber who opted out from "Brand A" still receives notifications from "Brand B" if they're a customer of both, **including** final notices and recovery confirmations.

### Audit Trail (MUST use single write path)

```python
# Final notice dispatch (engine, in schedule_retry)
write_audit_event(
    subscriber=str(subscriber.id),
    actor="engine",
    action="final_notice_dispatched",
    outcome="success",
    metadata={
        "decline_code": decision.decline_code,
        "retry_number": failure.retry_count + 1,
        "retry_cap": decision.retry_cap,
        "failure_id": str(failure.id),
    },
    account=account,
)

# Recovery confirmation: NO new audit at the dispatch site —
# the FSM post_transition signal already writes status_recovered,
# and the retry_succeeded event covers the recovery context.

# Inside the notification task (per send), reuse the existing
# notification_sent / notification_suppressed / notification_failed
# action names. Discriminate by metadata.email_type:
#   metadata={"email_type": "final_notice", ...}
#   metadata={"email_type": "recovery_confirmation", ...}
```

The audit grammar is intentionally identical across all three email types so dashboards / analytics / operator tools can group by `metadata.email_type`. Do **not** introduce `final_notice_sent` / `recovery_confirmation_sent` action strings.

### Gate Check Order (in both new notification tasks)

Identical to Story 4.1 (notifications.py:43-84):

1. `is_engine_active(account)` — Mid/Pro tier + DPA + engine mode set
2. `subscriber.email` non-blank (after strip)
3. `subscriber.excluded_from_automation` is `False`
4. `NotificationOptOut` exists for `(subscriber_email__iexact, account)`
5. Duplicate `NotificationLog` exists for `(failure, email_type, status="sent", account)` — fast-path; the partial unique constraint (Task 6) is the source of truth

### Project Structure Notes

**New files to create:**
```
backend/core/migrations/0014_notification_unique_sent_per_failure.py
```

**Files to modify:**
```
backend/core/services/email_templates.py         # +FinalNoticeTemplate, +RecoveryConfirmationTemplate, +2 dicts, +2 accessors
backend/core/services/email.py                   # +send_final_notice_email, +send_recovery_confirmation_email, +3 helpers, extract _render_email_shell, fix footer double-escape
backend/core/tasks/notifications.py              # +send_final_notice task, +send_recovery_confirmation task, generalize _log_suppression / _record_failure to take email_type
backend/core/services/recovery.py                # schedule_retry: dispatch send_final_notice on last retry, +final_notice_dispatched audit; process_retry_result: capture _safe_transition return, dispatch send_recovery_confirmation
backend/core/models/notification.py              # +partial UniqueConstraint on (failure, email_type) where status='sent'
backend/core/tests/test_services/test_email.py   # +final_notice + recovery_confirmation parametrized tests; +footer XSS guard
backend/core/tests/test_services/test_recovery.py # +TestFinalNoticeDispatch class, +TestRecoveryConfirmationDispatch class
backend/core/tests/test_tasks/test_notifications.py # +TestSendFinalNotice class, +TestSendRecoveryConfirmation class
backend/core/tests/test_models/test_notification.py # +unique constraint tests
```

No new dependencies. Do NOT touch `pyproject.toml`. (Resend SDK already installed in 4.1.)

### Dependencies

- **Upstream:** Story 4.1 done (Resend, `NotificationLog`, `NotificationOptOut`, `send_failure_notification`, gate sequence). Story 4.2 done (`Account.notification_tone`, `email_templates.py` + `ToneTemplate`, `_render_email_shell` does NOT yet exist — extract it in Task 2.3). Migration 0013 is the latest.
- **Downstream:** Story 4.4 (opt-out endpoint) will add the real opt-out URL — both new email types use the same placeholder `https://app.safenet.app/notifications/opt-out` until then. Story 4.4 will add a unique-per-recipient signed token to that URL; both new builders MUST accept the URL as a parameter (not hardcode it locally) so 4.4 is a one-line caller-site change.
- **Cross-story:** `Account.customer_update_url` capture (Story 2.1 follow-up) is still pending — both `send_notification_email` (4.1) and `send_final_notice_email` (this story) raise `SkipNotification` when the field is missing. `send_recovery_confirmation_email` does NOT depend on this field.
- **Open patches inherited from 4.2 review:** The footer-double-escape patch (decision-needed in 4.2 review findings) lands as part of Task 2.1 in this story. The 4.2 deferred TOCTOU patch (4.1 follow-up: unique constraint on `NotificationLog`) lands as Task 6 in this story.

### Testing Standards

- **Backend:** pytest. Mock Resend with `@patch("core.services.email.resend.Emails.send")` for the email-builder tests, or with `@patch("core.tasks.notifications.send_final_notice_email")` (and the recovery_confirmation equivalent) for the task-level tests. Reuse the autouse `_resend_configured`/`_fernet_key` fixtures from `test_services/test_email.py` and `test_tasks/test_notifications.py`.
- **Fixtures:** `mid_account`, `subscriber_with_email`, `failure` from existing `test_tasks/test_notifications.py:25-62`. `account`, `auth_client` from `core/tests/conftest.py`. `_make_decision` helper from `test_services/test_recovery.py:21-30`.
- **Coverage target:** every AC has at least one direct test. The trigger logic (Tasks 4 + 5) gets tested in `test_recovery.py` (NOT in `test_notifications.py`) because the dispatch decision is engine logic. The Celery-task gates (Task 3) get tested in `test_notifications.py`. The HTML/copy structure (Task 2) gets tested in `test_email.py`.
- **Critical regression guards:**
  1. Existing `TestSendFailureNotification` 10-test class must still pass after `_log_suppression` / `_record_failure` are generalized (Task 3.3).
  2. Existing `TestExecuteRecoveryAction`, `TestScheduleRetry`, `TestProcessRetryResult` classes in `test_recovery.py` must still pass after `process_retry_result` is modified (Task 5.1).
  3. The 4.1 escape tests in `test_email.py` must still pass after the `_render_email_shell` refactor (Task 2.3) — this is exactly the kind of thing the 4.2 review caught (snapshot brittleness).
- **Manual verification:** This story is backend-only. Local end-to-end verification: `docker compose up`, force a Mid-tier+DPA+autopilot account into the failed-payment scenario via `manage.py shell`, advance to last retry, observe `final_notice_dispatched` audit row + `NotificationLog(email_type="final_notice", status="sent")` row + Resend dashboard delivery; then mark retry success, observe `notification_sent` for `email_type="recovery_confirmation"`. Document this in Completion Notes.

### Previous Story Intelligence (4.2)

- **Footer double-escape (4.2 open patch)** at `email.py:103` — `html.escape(template.footer(escaped_company))` where `template.footer(...)` already received the escaped value. Renders `Acme &amp; Co` for company `Acme & Co`. Fix in this story (Task 2.1) for all three email types — single source of truth: pass raw `company_name`, escape exactly once at the f-string boundary. Add a parametric test asserting the entire `html_body` (header, body, **and footer**) contains `&lt;script&gt;` for input `<script>`.
- **`selectedTone` shadow state (4.2 open patch)** is frontend-only and out of scope here.
- **`useNotificationPreview` `encodeURIComponent` (4.2 open patch)** is frontend-only and out of scope.
- **`from typing import Callable` (4.2 patch)** already fixed at `email_templates.py:8` (uses `from collections.abc import Callable`). Match this in any new module-level imports.
- **`test_idempotent_when_unchanged` audit-only assertion (4.2 patch)** — when adding any new idempotency tests, assert **both** the no-DB-write side AND the no-audit-row side. Don't repeat the 4.2 mistake.
- **Empty `?tone=` falls back silently (4.2 decision-needed)** — not relevant to 4.3 (no new endpoint), but be aware: do not introduce empty-string-tolerant tone resolution in the new helpers. If `tone=""` is somehow passed in, `get_final_notice_template` and `get_recovery_confirmation_template` MUST fall back to `DEFAULT_TONE` exactly like `get_template` does.

### Git Intelligence (last 5 commits, 2026-04-15 → 2026-04-26)

```
1c7a131  Merge pull request #1 — review/3-2-autopilot-recovery-engine
f516e92  Story 4.2 review: apply 14 patches from adversarial code review
2ed02f5  Part2  (4.2 implementation, mid-stream)
9e704ea  Story 4.1 review: apply 21 patches from adversarial code review
7cafefc  Story 4.1: Resend integration for branded failure notification emails
```

Recent change patterns observed in the codebase:
- **Patch application is a separate commit** from initial implementation. Story 4.3 should follow this rhythm: implement first, run review, apply review patches in a follow-up commit. Don't squash.
- **Tests follow source file structure** — `services/foo.py` → `tests/test_services/test_foo.py`, `tasks/foo.py` → `tests/test_tasks/test_foo.py`. Maintain this 1:1 mapping. The new email-builder tests live in `test_services/test_email.py` (existing); the new task tests live in `test_tasks/test_notifications.py` (existing); the trigger-logic tests live in `test_services/test_recovery.py` (existing).
- **Every transactional write in the engine is wrapped in `transaction.atomic()`** — see `execute_retry.run` body and `process_retry_result` callers. Both new dispatches happen post-commit (`transaction.on_commit`), which sidesteps the wrapping requirement at the dispatch line itself but does NOT excuse callers from having an outer `atomic()` around the surrounding work.
- **`select_for_update()` is paired with `transaction.atomic()`** — already enforced at `retry.py:40-46` post-4.1 review. No new locks introduced in this story.

### Latest Tech Information

- **Resend Python SDK** (`resend==2.28.1` per Story 4.1 Completion Notes): the `resend.Emails.send({...})` API is unchanged. Response is a dict with an `id` field. The 4.1 patch at `email.py:186-188` already guards against missing-id responses (`if not msg_id: raise RuntimeError(...)`); both new builders inherit this guard verbatim.
- **Django 5.x partial unique indexes via `UniqueConstraint(condition=...)`** are fully supported on PostgreSQL — `manage.py sqlmigrate` produces `CREATE UNIQUE INDEX ... WHERE ...`. SQLite (used in some local test setups) supports `WHERE` in `CREATE UNIQUE INDEX` since 3.8. No special handling required.
- **`django-fsm`** transitions are pre-commit; the `post_transition` signal fires inside the `transition`-decorated method, before `subscriber.save()` returns. The existing `on_subscriber_status_transition` handler at `models/subscriber.py:87-99` writes audit synchronously — it does NOT use `transaction.on_commit`. This means the audit row is written even if the surrounding atomic block rolls back. This is a pre-existing minor bug (not in scope to fix here). Story 4.3's recovery confirmation dispatch deliberately uses `transaction.on_commit` to avoid the same pitfall — do **not** mirror the post_transition handler's bug.
- **Celery `@app.task(bind=True, max_retries=3, default_retry_delay=60)`** is the established pattern. Default exponential backoff is **NOT** automatic — the 4.1 task pattern uses `default_retry_delay=60` (linear). If you read elsewhere that exponential backoff is the default, that is incorrect for this codebase.

### References

- [Source: _bmad-output/epics.md — Epic 4, Story 4.3 lines 841-865]
- [Source: _bmad-output/prd.md — FR24 (line 501), FR25 (line 502), FR26 (line opt-out), FR28 (line shared domain), brand voice line 116-117 — final notice + recovery confirmation listed under "Mid-tier capabilities"]
- [Source: _bmad-output/architecture.md — Notification Service, Celery Task Patterns, Audit Trail (no Story-4.3-specific section, but the email-service / audit / FSM contracts apply)]
- [Source: _bmad-output/ux-design-specification.md — Sophie's Journey 4 (line 733-771), recovery confirmation brevity (line 771), tone consistency (line 766-771)]
- [Source: _bmad-output/4-1-resend-integration-branded-failure-notification-email.md — Resend integration, gate-check order, customer_update_url skip pattern, deferred TOCTOU patch (line 105), generalization-friendly logging shape]
- [Source: _bmad-output/4-2-tone-selector-settings-live-notification-preview.md — TONE_TEMPLATES extension hint (Dependencies line 322), open footer-double-escape patch, single-source-of-truth rule, 5-test parametrize pattern]
- [Source: backend/core/services/email.py — `_build_html_body` shell to extract, `_build_subject`, `_build_from_field`, `_sanitize_header`, `_HEADER_INJECTION_CHARS`, `SkipNotification`, `send_notification_email` end-to-end pattern]
- [Source: backend/core/services/email_templates.py — `ToneTemplate` dataclass (do NOT widen), `get_template` accessor pattern, `TONE_TEMPLATES` dict, `DEFAULT_TONE`]
- [Source: backend/core/tasks/notifications.py — `send_failure_notification` 5-gate sequence, `_log_suppression`, `_record_failure`, retry/DLL pattern]
- [Source: backend/core/services/recovery.py — `schedule_retry` (final notice trigger site, lines 140-198), `process_retry_result` (recovery confirmation trigger site, lines 201-251), `_safe_transition` (return value semantics, lines 33-61)]
- [Source: backend/core/tasks/polling.py — `transaction.on_commit(lambda fid=...: ...delay(fid))` dispatch pattern, lines 132-136]
- [Source: backend/core/models/notification.py — `EMAIL_TYPE_CHOICES` already includes `final_notice` and `recovery_confirmation` (lines 5-9); `NOTIFICATION_STATUS_CHOICES` (lines 11-15)]
- [Source: backend/core/models/subscriber.py — FSM `recover` transition (line 32-35), `mark_passive_churn` (37-40), `post_transition` signal handler (87-99)]
- [Source: backend/core/engine/state_machine.py — `STATUS_ACTIVE`, `STATUS_RECOVERED`, `STATUS_PASSIVE_CHURN` constants]
- [Source: backend/core/engine/rules.py — `DECLINE_RULES`; max `retry_cap=3` for `insufficient_funds`, `retry_cap=2` for `processing_error`/`issuer_unavailable`, `retry_cap=1` for `try_again_later`. Final-notice tests should parametrize across `retry_cap ∈ {1, 2, 3}`.]
- [Source: backend/core/tests/conftest.py — `account`, `auth_client`, `user`, `client` fixtures]
- [Source: backend/core/tests/test_tasks/test_notifications.py — fixture and class structure to mirror, lines 1-90]
- [Source: backend/core/tests/test_services/test_recovery.py — `_make_decision` helper, fixture structure, lines 1-80]

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Claude Opus 4.7)

### Debug Log References

- Full regression suite: 469 passed, 10 failed — all 10 failures are pre-existing on `main` (verified via `git stash` + re-run); zero new regressions from this story.
- New tests: 32 in `test_tasks/test_notifications.py` (10 existing + 22 new), 25 in `test_services/test_recovery.py` (12 existing + 13 new), 83 in `test_services/test_email.py` (40 existing + 43 new), 10 in `test_models/test_notification.py` (7 existing + 3 new constraint tests). All passing.

### Completion Notes List

- **Templates (Task 1):** Added `FinalNoticeTemplate` and `RecoveryConfirmationTemplate` frozen dataclasses with verbatim canonical tone copy. `RecoveryConfirmationTemplate` has no `cta_label` field; body cap enforced by construction (Professional/Friendly: 2 paragraphs; Minimal: 1).
- **Email builders (Task 2):** Extracted `_render_email_shell(escaped_company, inner_html)` from `_build_html_body` so all three email types share identical outer chrome. Failure-notice rendering is byte-equivalent (verified by existing escape tests). Added `send_final_notice_email` (raises `SkipNotification` on missing `customer_update_url`) and `send_recovery_confirmation_email` (no `customer_update_url` guard, no CTA block in HTML). Footer single-escape was already correct in current code; preserved across all three types.
- **Celery tasks (Task 3):** Generalized `_log_suppression(*, reason, email_type)` and `_record_failure(*, email_type, task_name)`. Added `send_final_notice` and `send_recovery_confirmation` Celery tasks with the same 5-gate sequence as `send_failure_notification`. Wrapped success-path `NotificationLog.create(status="sent")` in `try/except IntegrityError` → `_log_suppression(reason="duplicate_race")` so the partial unique constraint is the source of truth.
- **Trigger logic (Tasks 4 & 5):** In `schedule_retry`, dispatch `send_final_notice` via `transaction.on_commit` when `failure.retry_count + 1 == decision.retry_cap`, with status guard (`STATUS_ACTIVE` only) and `final_notice_dispatched` audit. In `process_retry_result`, captured `_safe_transition` return value and dispatch `send_recovery_confirmation` only when transition is true.
- **Migration (Task 6):** Added partial `UniqueConstraint(fields=["failure", "email_type"], condition=Q(status="sent"))` and migration `0014_notification_unique_sent_per_failure.py`. Allows multiple `suppressed`/`failed` rows per `(failure, email_type)` (matches Story 4.1 design where gate-fail rows can repeat across polling cycles).
- **AC verification:** AC1 covered by `TestFinalNoticeDispatch.test_dispatched_on_last_retry`. AC2 by `TestRecoveryConfirmationDispatch.test_dispatched_on_successful_recover` + `test_not_dispatched_when_transition_blocked`. AC3 by `test_not_dispatched_when_subscriber_inactive`. AC4 by escape and gate tests across all three email types. AC5 by `test_skip_when_no_customer_update_url` and `test_sends_without_customer_update_url`. AC6 by `test_retry_on_api_error` and `test_dead_letter_on_exhausted_retries`. AC7 by `# 5-minute SLA` comment at the dispatch call-site in `recovery.py`.
- **No frontend changes** — story is engine + email-template only. Notification preview endpoint deliberately not widened (per Dev Notes).
- **Manual verification deferred** — no Resend API key configured locally. Production verification will rely on `final_notice_dispatched` audit row + `NotificationLog(email_type=..., status="sent")` row + Resend dashboard.

### File List

**New files:**
- `backend/core/migrations/0014_notification_unique_sent_per_failure.py`

**Modified files:**
- `backend/core/services/email_templates.py`
- `backend/core/services/email.py`
- `backend/core/tasks/notifications.py`
- `backend/core/services/recovery.py`
- `backend/core/models/notification.py`
- `backend/core/tests/test_services/test_email.py`
- `backend/core/tests/test_services/test_recovery.py`
- `backend/core/tests/test_tasks/test_notifications.py`
- `backend/core/tests/test_models/test_notification.py`

## Change Log

| Date | Author | Description |
|------|--------|-------------|
| 2026-04-27 | Dev Agent (Opus 4.7) | Initial implementation of Story 4.3: final notice + recovery confirmation emails, 5-gate Celery tasks, schedule_retry / process_retry_result dispatch, partial unique constraint migration. All 10 tasks complete; 81 new tests added (22 task + 13 trigger + 43 email + 3 constraint); zero regressions. Status → review. |
| 2026-04-27 | Code Review (Opus 4.7) | Adversarial review applied: 9 patches (race-window telemetry, schedule_retry idempotency guard, FSM-drift gate, migration backfill, whitespace-URL strip, 4 test improvements). 9 deferred to backlog. 1 decision dismissed (recovery-confirmation opt-out per AC 4). 18 noise findings dismissed. 150 in-scope tests pass. Status → done. |

### Review Findings (2026-04-27)

Three-layer adversarial review (Blind Hunter / Edge Case Hunter / Acceptance Auditor). Acceptance Auditor confirmed all 7 ACs and 10 tasks are met; deviations found (guard placement nesting, test counts at template level rather than rendered HTML) are semantically equivalent and dismissed.

**Decisions resolved:**

- Pre-send IntegrityError race window → resolved as a patch (record `resend_message_id` in the `suppressed_duplicate` row so the second send remains auditable; do not redesign the dispatch sequence).
- Recovery confirmation respects `NotificationOptOut` → dismissed; AC 4 explicitly requires the full gate sequence, current behavior is correct.

**Patches (applied):**

- [x] [Review][Patch] Capture `resend_message_id` in the `suppressed_duplicate` `NotificationLog` row when `IntegrityError` fires after `Resend.send` succeeds. Extended `_log_suppression` with an `extra_metadata` parameter and pass `{"resend_message_id": msg_id}` from all three duplicate-race catch blocks. [`backend/core/tasks/notifications.py`]
- [x] [Review][Patch] `schedule_retry` final-notice idempotency guard — pre-check `NotificationLog` for any existing `sent` or `suppressed` row for `(failure, email_type='final_notice')` before registering the on-commit dispatch. [`backend/core/services/recovery.py`]
- [x] [Review][Patch] Added Gate 6 in `_passes_gates`: when `email_type == "final_notice"`, suppress the send if `subscriber.status != STATUS_ACTIVE` (FSM-drift recheck at task time). [`backend/core/tasks/notifications.py`]
- [x] [Review][Patch] Migration 0014 now runs a defensive `dedupe_existing_sent_rows` `RunPython` before `AddConstraint` — keeps the oldest `sent` row per `(failure, email_type)` so deploy does not fail on pre-existing 4.1 duplicates. [`backend/core/migrations/0014_notification_unique_sent_per_failure.py`]
- [x] [Review][Patch] `customer_update_url` whitespace-only check — added `.strip()` to the `getattr` result in both `send_notification_email` and `send_final_notice_email`. [`backend/core/services/email.py`]
- [x] [Review][Patch] `test_unique_sent_per_failure_constraint` now asserts the constraint name via `pytest.raises(IntegrityError, match="unique_sent_notification_per_failure_email_type")`. [`backend/core/tests/test_models/test_notification.py`]
- [x] [Review][Patch] `test_idempotent_per_failure` documents the FSM-based idempotency mechanism with a clarifying comment and adds an explicit `subscriber.status == STATUS_RECOVERED` assertion between calls. [`backend/core/tests/test_services/test_recovery.py`]
- [x] [Review][Patch] `test_skip_when_no_customer_update_url` now patches `resend.Emails.send` (not `send_final_notice_email`) so the real `SkipNotification` raise path inside the email service is exercised. [`backend/core/tests/test_tasks/test_notifications.py`]
- [x] [Review][Patch] `test_writes_final_notice_dispatched_audit` now asserts all four audit metadata fields: `retry_cap`, `retry_number`, `decline_code`, `failure_id`. [`backend/core/tests/test_services/test_recovery.py`]

**Deferred (pre-existing or out of scope for 4.3):**

- [x] [Review][Defer] `_record_failure` swallows all exceptions during DLL / NotificationLog writes — silent failures invisible to alerting. Pre-existing pattern from 4.1; address as a notifications-resilience epic. [`backend/core/tasks/notifications.py:_record_failure`]
- [x] [Review][Defer] `customer_update_url` accepts `javascript:` and other dangerous schemes — `html.escape(quote=True)` does not block scheme abuse on `<a href>`. Should be validated at account-update boundary. Pre-existing across all CTA-bearing email types. [`backend/core/services/email.py:223`]
- [x] [Review][Defer] `resend.Emails.send` has no client-side timeout — worker stall past Celery visibility timeout causes redelivery and amplifies the race window. Pre-existing across all three send paths. [`backend/core/services/email.py:296-300, 352-357, 402-407`]
- [x] [Review][Defer] `NotificationLog.email_type` has no `choices=` / CHECK constraint — typos silently create new categories. Pre-existing from 4.1 schema. [`backend/core/models/notification.py:NotificationLog`]
- [x] [Review][Defer] `is_last_retry = (retry_count + 1) == retry_cap` is `==`, not `>=` — fails to fire if `retry_count` ever exceeds `retry_cap` due to data corruption or mid-flight rule edit. Edge case; out of scope. [`backend/core/services/recovery.py:204`]
- [x] [Review][Defer] `retry_cap` change between retries (admin edits the rule mid-flight) skews `is_last_retry` — final notice fires too early or never. Out of scope. [`backend/core/services/recovery.py:204`]
- [x] [Review][Defer] `_safe_transition` raises non-`TransitionNotAllowed` (DB error) after `retry_count` is saved — `retry_count` persisted but FSM stuck. Broader DB-resilience concern. [`backend/core/services/recovery.py:_safe_transition`]
- [x] [Review][Defer] `NotificationLog.objects.create` raises non-`IntegrityError` after Resend already sent — audit divergence (sent email but no DB row). Broader DB-resilience concern. [`backend/core/tasks/notifications.py:113-121`]
- [x] [Review][Defer] `resend.Emails.send` may return a dict missing `"id"` key or raise an SDK-specific exception class — current `dict["id"]` access and broad `except Exception` work but are SDK-contract assumptions. [`backend/core/services/email.py:_send_resend_email`]
