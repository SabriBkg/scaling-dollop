# Story 4.1: Resend Integration & Branded Failure Notification Email

Status: review

## Story

As a Mid-tier founder,
I want SafeNet to automatically send a branded payment failure notification to my subscriber using my SaaS name,
So that my subscriber receives a professional, human-feeling email that feels like it came from me.

## Acceptance Criteria

1. **Given** the Resend email provider is configured
   **When** a notification action is triggered by the engine (classified_action is `notify_only` or `retry_notify`)
   **Then** the email is sent from the SafeNet-managed shared sending domain (`payments.safenet.app`) with the client's brand name in the `From` field (e.g., `"ProductivityPro via SafeNet" <notifications@payments.safenet.app>`) (FR28)
   **And** the email contains: a clear explanation of the failure (plain language via `DECLINE_CODE_LABELS`, no Stripe jargon), a single card-update CTA linking to the Stripe customer portal, an opt-out link, and the client's brand name throughout (FR22, FR26)

2. **Given** a `card_expired` failure
   **When** the notification email is sent
   **Then** the email explicitly states: "Your access continues while you update your details"
   **And** the subject line is understated — no urgency language, no threat of account suspension

3. **Given** a notification send attempt fails (Resend API error)
   **When** the task catches the exception
   **Then** it retries up to 3 times with exponential backoff
   **And** if all retries fail, the failure is written to `DeadLetterLog` and the audit log records `{action: "notification_failed", outcome: "failed"}` (NFR-R3, NFR-R5)

4. **Given** a subscriber has opted out (Story 4.4 — stub the check now)
   **When** the engine attempts to send a notification
   **Then** the notification is suppressed and the suppression is logged to the audit trail

5. **Given** a Free-tier account
   **When** the engine processes a failure with a notify action
   **Then** no notification email is sent — notifications require Mid/Pro tier with DPA accepted and engine mode set (`is_engine_active()` gate)

6. **Given** a subscriber with no email address (blank `email` field)
   **When** a notification action is triggered
   **Then** the notification is skipped and an audit event records `{action: "notification_skipped", metadata: {reason: "no_email"}}`

## Tasks / Subtasks

- [x] Task 1: Add `resend` Python package (AC: all)
  - [x] 1.1 `poetry add resend` in backend
  - [x] 1.2 Add `RESEND_API_KEY` and `SAFENET_SENDING_DOMAIN` to `.env.example` and `settings/base.py`
  - [x] 1.3 Add `RESEND_API_KEY` env var to `docker-compose.yml` web + worker services

- [x] Task 2: Create `NotificationLog` model (AC: 1, 3)
  - [x] 2.1 New file: `core/models/notification.py` — `NotificationLog(TenantScopedModel)` with fields: `subscriber` FK, `failure` FK (nullable), `email_type` (CharField: `failure_notice`, `final_notice`, `recovery_confirmation`), `resend_message_id` (CharField, nullable), `status` (CharField: `sent`, `failed`, `suppressed`), `metadata` (JSONField)
  - [x] 2.2 Stub `NotificationOptOut(TenantScopedModel)` model with fields: `subscriber_email` (EmailField), `created_at` — this is the opt-out record for Story 4.4
  - [x] 2.3 Register both models in `core/models/__init__.py`
  - [x] 2.4 Create and run migration

- [x] Task 3: Create email service (AC: 1, 2, 3)
  - [x] 3.1 New file: `core/services/email.py` — `send_notification_email(subscriber, failure, account)` function
  - [x] 3.2 Use Resend Python SDK: `resend.Emails.send()` with params: `from_` as `"{company_name} via SafeNet" <notifications@{SAFENET_SENDING_DOMAIN}>`, `to` subscriber.email, `subject`, `html` body
  - [x] 3.3 Build HTML email body inline (simple, clean HTML — no template engine needed at MVP): failure explanation using `DECLINE_CODE_LABELS[decline_code]`, card-update CTA button linking to Stripe customer portal URL (`https://billing.stripe.com/p/login/{stripe_user_id}`), opt-out link (placeholder URL for Story 4.4), client brand name throughout
  - [x] 3.4 Special handling for `card_expired`/`expired_card`: include "Your access continues while you update your details" text, understated subject line
  - [x] 3.5 Return Resend message ID on success, raise on failure

- [x] Task 4: Create notification Celery task (AC: 1, 2, 3, 4, 5, 6)
  - [x] 4.1 New file: `core/tasks/notifications.py` — `send_failure_notification(failure_id)` task
  - [x] 4.2 Task decorator: `@app.task(bind=True, max_retries=3, default_retry_delay=60)` — follows established pattern
  - [x] 4.3 Gate checks (in order): `is_engine_active(account)`, subscriber has email, opt-out check (stub: query `NotificationOptOut.objects.filter(subscriber_email=subscriber.email, account=account).exists()`), subscriber.excluded_from_automation is False
  - [x] 4.4 On success: create `NotificationLog` with status `sent`, write audit event `{action: "notification_sent", outcome: "success"}`
  - [x] 4.5 On failure after retries exhausted: create `DeadLetterLog`, create `NotificationLog` with status `failed`, write audit event `{action: "notification_failed", outcome: "failed"}`
  - [x] 4.6 On suppression (opt-out or gate fail): create `NotificationLog` with status `suppressed`, write audit event `{action: "notification_suppressed", outcome: "skipped", metadata: {reason: ...}}`

- [x] Task 5: Integrate notification dispatch into engine pipeline (AC: 1)
  - [x] 5.1 In `core/tasks/polling.py` `poll_account_failures`: immediately after `ingest_failed_payment()` returns (before the autopilot/supervised branching), if `classified_action` includes notification (`notify_only` or `retry_notify`), dispatch `send_failure_notification.delay(failure.id)` — notification fires regardless of engine mode
  - [x] 5.2 In `core/tasks/scanner.py`: do NOT trigger notifications for retroactive scan results — these are historical failures, not real-time events
  - [x] 5.3 In `core/tasks/retry.py`: do NOT duplicate notification here — notification is triggered at failure detection time, not at retry time (Story 4.3 will add recovery confirmation)

- [x] Task 6: Backend tests (AC: all)
  - [x] 6.1 `core/tests/test_services/test_email.py` — test email body generation, From field formatting, card_expired special case, missing email handling
  - [x] 6.2 `core/tests/test_tasks/test_notifications.py` — test gate checks (tier, DPA, opt-out, excluded, no-email), success path with mock Resend, retry on API error, dead-letter on exhausted retries, audit event creation
  - [x] 6.3 `core/tests/test_models/test_notification.py` — model creation, tenant scoping

## Dev Notes

### Architecture Compliance

- **Resend SDK**: Use `resend` Python package (official SDK). Initialize with `resend.api_key = settings.RESEND_API_KEY` at module level in `core/services/email.py`.
- **Sending domain**: Shared domain `payments.safenet.app` for all Mid-tier accounts (FR28). From field format: `"{account.company_name} via SafeNet" <notifications@payments.safenet.app>`. The subscriber (Sophie) sees Marc's brand name, never SafeNet branding directly.
- **Email content**: Plain HTML — no Django template engine, no Jinja. Build the HTML string in `email.py`. Keep it simple, clean, mobile-responsive. Two key elements: failure explanation + card-update CTA button.
- **Stripe customer portal link**: Use `https://billing.stripe.com/p/login/{stripe_user_id}` where `stripe_user_id` comes from `StripeConnection.stripe_user_id`. This is Stripe's hosted billing portal — no custom page needed.

### Celery Task Pattern (MUST follow)

```python
@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_failure_notification(self, failure_id: int):
    logger.info(f"[send_failure_notification] START failure_id={failure_id}")
    try:
        # ... gate checks, send email, audit log
        logger.info(f"[send_failure_notification] COMPLETE failure_id={failure_id}")
    except Exception as exc:
        logger.error(f"[send_failure_notification] FAILED failure_id={failure_id} error={exc}")
        if self.request.retries >= self.max_retries:
            DeadLetterLog.objects.create(task_name="send_failure_notification", account=failure.account, error=str(exc))
        raise self.retry(exc=exc)
```

### Tenant Isolation

- `NotificationLog` and `NotificationOptOut` MUST inherit from `TenantScopedModel` (required `account` FK, scoped queries enforced)
- All queries use `.for_account(account_id)` or `.filter(account=account)` — never raw `.objects.all()`
- Opt-out check is scoped per subscriber_email + account pair (not globally)

### Audit Trail (MUST use single write path)

```python
write_audit_event(
    subscriber=str(subscriber.id),
    actor="engine",
    action="notification_sent",  # or "notification_failed", "notification_suppressed", "notification_skipped"
    outcome="success",           # or "failed", "skipped"
    metadata={"email_type": "failure_notice", "decline_code": failure.decline_code, "resend_message_id": msg_id},
    account=account,
)
```

### API Response Envelope

No new API endpoints in this story — all work is backend/Celery. Future stories (4.2) will add settings endpoints.

### Gate Check Order (in notification task)

1. `is_engine_active(account)` — returns False for Free tier, no DPA, or no engine mode
2. `subscriber.email` is not blank
3. `subscriber.excluded_from_automation` is False
4. `NotificationOptOut` check — stub for Story 4.4, but wire it now so the check exists
5. Duplicate check — don't send if `NotificationLog` already has a `sent` entry for this failure_id + email_type combo

### Existing Code to Reuse (DO NOT reinvent)

| What | Where | Usage |
|------|-------|-------|
| `DECLINE_CODE_LABELS` | `core/engine/labels.py` | Human-readable failure explanation text |
| `get_rule()` | `core/engine/rules.py` | Check `classified_action` to determine if notification needed |
| `is_engine_active()` | `core/services/tier.py` | Gate: Mid/Pro + DPA + engine mode |
| `write_audit_event()` | `core/services/audit.py` | Single audit write path — never inline |
| `DeadLetterLog` | `core/models/dead_letter.py` | Failed task recording (NFR-R5) |
| `TenantScopedModel` | `core/models/base.py` | Base class for all new models |
| `StripeConnection.stripe_user_id` | `core/models/account.py` | For Stripe customer portal URL |
| `Account.company_name` | `core/models/account.py` | Brand name in From field and email body |

### What NOT to Do

- Do NOT add Celery beat schedule entries — notifications are event-driven (triggered by polling/engine), not scheduled
- Do NOT send notifications for retroactive scan results (scanner.py) — those are historical
- Do NOT build a Django template system — inline HTML in `email.py` is sufficient for MVP
- Do NOT add frontend components — this story is backend-only
- Do NOT implement tone selection — that's Story 4.2 (use a single default "Professional" tone for now)
- Do NOT implement final notice or recovery confirmation — that's Story 4.3
- Do NOT build the opt-out endpoint — that's Story 4.4 (just stub the model and the check)

### Project Structure Notes

New files to create:
```
backend/core/models/notification.py     # NotificationLog + NotificationOptOut models
backend/core/services/email.py          # Resend integration service
backend/core/tasks/notifications.py     # send_failure_notification Celery task
backend/core/tests/test_services/test_email.py
backend/core/tests/test_tasks/test_notifications.py
backend/core/tests/test_models/test_notification.py
```

Files to modify:
```
backend/core/models/__init__.py         # Register new models
backend/core/tasks/polling.py           # Dispatch notification after failure ingestion
backend/pyproject.toml                  # Add resend dependency
backend/safenet_backend/settings/base.py # Add RESEND_API_KEY setting
docker-compose.yml                      # Add RESEND_API_KEY to web + worker env
.env.example                            # Add RESEND_API_KEY placeholder
```

### Dependencies

- **Upstream**: Epics 1-3 complete (all done). Polling, engine, FSM, tier gating all in place.
- **Downstream**: Stories 4.2 (tone selector), 4.3 (final notice + recovery confirmation), 4.4 (opt-out endpoint), 4.5 (password reset) all build on the Resend infrastructure from this story.

### Testing Standards

- **Backend**: pytest with Django test client. Mock Resend API calls with `unittest.mock.patch`. Follow patterns in `core/tests/test_tasks/test_polling.py`.
- **Fixtures**: Use `conftest.py` fixtures for Account, StripeConnection, Subscriber, SubscriberFailure. Add new fixtures for NotificationLog.
- **Key test scenarios**: tier gating (Free tier blocked), DPA not accepted (blocked), no email (skipped), opt-out (suppressed), excluded subscriber (suppressed), Resend API error (retry + dead-letter), successful send (NotificationLog created, audit event written), card_expired special messaging, duplicate prevention.

### References

- [Source: _bmad-output/epics.md — Epic 4, Story 4.1]
- [Source: _bmad-output/architecture.md — Notification Service, Celery Task Patterns, Audit Trail]
- [Source: _bmad-output/ux-design-specification.md — Sophie's Journey, Notification Tone, Branded Email Design]
- [Source: _bmad-output/prd.md — FR22, FR23, FR24, FR25, FR26, FR27, FR28, NFR-R3, NFR-R5]
- [Source: core/services/tier.py — is_engine_active() gate]
- [Source: core/engine/labels.py — DECLINE_CODE_LABELS for human-readable explanations]
- [Source: core/engine/rules.py — classified_action determination]
- [Source: core/models/account.py — Account.company_name, StripeConnection.stripe_user_id]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- Fixed test_email.py: Django doesn't allow assigning MagicMock to OneToOneField reverse — switched to fully mocked account
- Fixed test_notifications.py dead-letter test: Celery task `request` property is read-only — used `send_failure_notification.run.__func__` to call with mock self
- Fixed test_polling.py regression: New `send_failure_notification.delay()` call in polling tried to connect to Redis — added autouse fixture to mock it

### Completion Notes List
- Installed `resend` v2.28.1 via Poetry
- Created `NotificationLog` and `NotificationOptOut` models (TenantScopedModel) with migration 0012
- Built email service with branded From field, inline HTML, card_expired special handling, CTA button linking to Stripe customer portal
- Created Celery task with 5 gate checks: engine active, email present, not excluded, not opted out, no duplicate
- Task follows established retry pattern (max_retries=3, exponential backoff) with dead-letter on exhaustion
- Integrated notification dispatch into polling pipeline at failure ingestion time (before recovery branching)
- Confirmed scanner.py and retry.py are NOT modified (per spec)
- All 33 new tests pass; no regressions in existing 337 tests (10 pre-existing failures unrelated to this story)

### File List
- `backend/core/models/notification.py` — NEW: NotificationLog + NotificationOptOut models
- `backend/core/models/__init__.py` — MODIFIED: registered new models
- `backend/core/services/email.py` — NEW: Resend email integration service
- `backend/core/tasks/notifications.py` — NEW: send_failure_notification Celery task
- `backend/core/tasks/polling.py` — MODIFIED: dispatch notification after failure ingestion
- `backend/safenet_backend/settings/base.py` — MODIFIED: added RESEND_API_KEY and SAFENET_SENDING_DOMAIN settings
- `backend/pyproject.toml` — MODIFIED: added resend dependency
- `backend/poetry.lock` — MODIFIED: updated lock file
- `.env.example` — MODIFIED: added RESEND_API_KEY and SAFENET_SENDING_DOMAIN
- `backend/core/migrations/0012_notification_models.py` — NEW: migration for notification models
- `backend/core/tests/test_services/test_email.py` — NEW: 16 tests for email service
- `backend/core/tests/test_tasks/test_notifications.py` — NEW: 10 tests for notification task
- `backend/core/tests/test_models/test_notification.py` — NEW: 7 tests for notification models
- `backend/core/tests/test_tasks/test_polling.py` — MODIFIED: added fixture to mock notification dispatch

### Change Log
- 2026-04-15: Implemented Story 4.1 — Resend integration, branded failure notification email, notification Celery task with gate checks, polling pipeline integration, 33 new tests
