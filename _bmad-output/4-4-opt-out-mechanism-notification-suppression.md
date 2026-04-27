# Story 4.4: Opt-Out Mechanism & Notification Suppression

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a subscriber receiving SafeNet-dispatched payment notifications,
I want to click an opt-out link in any email and confirm a one-click unsubscribe,
So that I stop receiving payment notifications from that specific SaaS without affecting my account access or my notification preferences with other SaaS clients.

## Acceptance Criteria

1. **Given** every notification email sent by SafeNet (`failure_notice`, `final_notice`, `recovery_confirmation`)
   **When** the email body is rendered
   **Then** the existing `<a href="...">Unsubscribe from payment notifications</a>` link points at a fully qualified opt-out URL of shape `{SAFENET_BASE_URL}/optout/{signed_token}/`
   **And** the `signed_token` is generated via `django.core.signing.TimestampSigner.sign_object({"email": subscriber_email_lowered, "account_id": account.id})` (stateless — no DB row, signed with `SECRET_KEY`)
   **And** the **same token-builder helper** is used by all three send paths (`send_notification_email`, `send_final_notice_email`, `send_recovery_confirmation_email`) — the placeholder string `"https://app.safenet.app/notifications/opt-out"` is replaced in **every** call site (email.py:279, 337, 388 and account.py:283 — the notification_preview view)
   **And** the notification_preview endpoint renders the email with a non-functional **preview** token so the live preview reads identically to a real email but the token never resolves to a real opt-out (FR26)

2. **Given** a subscriber clicks the opt-out link in any notification email
   **When** the unauthenticated `GET /optout/{token}/` endpoint receives the request
   **Then** the token is decoded via `TimestampSigner.unsign_object(token, max_age=None)` — opt-out links **never expire** (transactional / contractual flow) — and the `(email, account_id)` payload is extracted
   **And** the response is an HTML confirmation page (inline HttpResponse, content_type="text/html") that:
   - Reads, in plain text: `"Confirm: unsubscribe from payment notifications for {company_name}"`
   - Renders a `<form method="POST">` with a single visible button `"Unsubscribe"` (no other inputs)
   - Includes the company name from `account.company_name or "this service"`
   - Is wrapped in the **same `_render_email_shell`** chrome that emails use, for visual consistency (extracted in 4.3 — the brand header `<h2>` shows `company_name`)
   - Returns HTTP 200
   - Includes `<meta name="robots" content="noindex,nofollow">` so search engines never index the page
   **And** if the token is invalid, expired (defensive — even though `max_age=None`, malformed tokens raise `BadSignature`), or the referenced `Account` no longer exists, the response is a 200 OK with a generic message **"This unsubscribe link is no longer valid. If you continue to receive emails, contact the sender directly."** (deliberately ambiguous — does NOT confirm or deny existence of the email/account, prevents enumeration)
   **And** the GET handler is **idempotent and read-only** — it MUST NOT create a `NotificationOptOut` row (defends against email-scanner / Gmail / Outlook link-prefetching automatically opting users out)
   **And** the GET handler is `@csrf_exempt` and `@require_http_methods(["GET", "POST"])`

3. **Given** the subscriber clicks the "Unsubscribe" button on the confirmation page
   **When** the `POST /optout/{token}/` request is received
   **Then** the same token-decode happens (re-decoded server-side — never trust hidden form fields for the email/account_id)
   **And** the action attempts `NotificationOptOut.objects.create(account=account, subscriber_email=email)` — a new row is created OR an `IntegrityError` is caught (idempotent — re-clicking on a different device, replaying the link, double-submit all collapse to a single opt-out row per the existing `unique_opt_out_per_account` constraint at notification.py:62-67)
   **And** an audit event is written via `write_audit_event(subscriber=<lookup or None>, actor="subscriber", action="notification_opted_out", outcome="success", metadata={"subscriber_email": email, "account_id": account.id, "company_name": account.company_name}, account=account)` — the actor is `"subscriber"` (a new actor value in addition to the existing `"engine" | "operator" | "client"` — extend the audit grammar to include `subscriber` as a fourth allowed value)
   **And** the response is an HTML success page (200 OK) reading: `"You've been unsubscribed from payment notifications for {company_name}."` (canonical copy — exact phrasing per epic-spec line 879) — wrapped in the same `_render_email_shell` brand header
   **And** the success response is identical whether the row was newly created OR the `IntegrityError` (already-opted-out) path fired — the user always sees the success page (FR26)
   **And** the audit event is **only written on the create path**, not on the duplicate `IntegrityError` path — replaying an opt-out should not produce duplicate audit rows for the same `(email, account_id)` (use a `try ... except IntegrityError: skip_audit` pattern; do NOT introduce an `if exists()` pre-check — that is TOCTOU-vulnerable and the existing 4.3 partial-unique-constraint design rejected pre-checks)

4. **Given** a `NotificationOptOut(account=A, subscriber_email=sub@x.com)` row exists
   **When** the engine attempts to dispatch any of the three notification email types for that subscriber email + account
   **Then** the existing **Gate 4** in `_passes_gates` (notifications.py:64-69) catches the opt-out via `NotificationOptOut.objects.filter(subscriber_email__iexact=subscriber.email.strip(), account=account).exists()` — this gate already exists and works for all three email types; **no logic change required** in `_passes_gates`, only verification
   **And** the suppression writes a `NotificationLog(status="suppressed", metadata={"reason": "opt_out", "email_type": <type>}, account=A)` row (existing `_log_suppression` behaviour — confirmed by reading notifications.py:63-69)
   **And** the audit row reads `{action: "notification_suppressed", actor: "engine", outcome: "skipped", metadata: {reason: "opt_out", failure_id: ..., email_type: <type>}, account: A}` (existing `_log_suppression` behaviour)
   **And** the suppression is **scoped per (subscriber_email, account_id)** pair — a subscriber who opted out from "Brand A" still receives notifications from "Brand B" if they're a customer of both (verify with a multi-account regression test)
   **And** the opt-out check **must occur before every notification action** — Gate 4 runs in every branch of every email task; no notification is ever sent without this check

5. **Given** the existing `customer_update_url` SkipNotification guard (4.1 / 4.3) in `send_notification_email` and `send_final_notice_email`
   **When** a subscriber is opted out AND `customer_update_url` is empty
   **Then** the gate-check sequence at notifications.py:39-94 runs **before** the email-builder is called, so the opt-out gate fires first and the SkipNotification path is never reached. Both produce a `NotificationLog(status="suppressed")` row, but with different `metadata.reason` values (`"opt_out"` vs `"skip_permanent"`). The opt-out check **takes precedence** by virtue of running earlier in the gate sequence

6. **Given** SafeNet's GDPR/transactional classification (PRD line 504: "All SafeNet notifications are classified as transactional messages (contractual necessity) — a standard marketing opt-out from the client's own communications does not suppress SafeNet notifications")
   **When** a subscriber opts out via SafeNet's link
   **Then** the opt-out is **scoped to SafeNet-dispatched emails only** — `NotificationOptOut` is the source of truth, and there is **no inbound integration** with the client's own email service marketing-opt-out lists
   **And** documentation (Dev Notes section "GDPR Classification") explicitly captures this contract so future operator queries (e.g. "this user opted out of marketing in Brand A's CRM, why are they still getting SafeNet emails?") have a canonical answer
   **And** there is **no** "global opt-out" that covers all accounts at once — opt-out is per (subscriber_email, account_id), per FR27 and AC 4

7. **Given** observability requirements
   **When** the opt-out flow runs end-to-end
   **Then** structured logging captures: `[optout_view] GET token_valid=<bool> account_id=<id|None>`, `[optout_view] POST opted_out account_id=<id> already_existed=<bool>`, `[optout_view] INVALID_TOKEN error=<exc_class>` — log lines mirror the established `[task_name] EVENT key=value` shape used in tasks/notifications.py
   **And** the unsign-failure path logs at `WARNING` level with `exception_type` but **never** logs the raw token (defends against accidental token leak in Sentry / log aggregator)
   **And** invalid-token responses are **not** rate-limited at MVP — a real abuser can mint random tokens cheaply, but the unsign cost is in microseconds and PostgreSQL is never touched. (Document as a deferred follow-up; do not block on it.)

## Tasks / Subtasks

- [x] **Task 1: Backend — Token signing helper** (AC: 1, 2, 3)
  - [x] 1.1 Create new module `backend/core/services/optout_token.py` with two functions:
    ```python
    from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

    _SALT = "safenet.notifications.optout"

    def build_optout_token(subscriber_email: str, account_id: int) -> str:
        """Sign a stateless opt-out token. Stateless: no DB row needed.
        Email is lower-cased + stripped before signing — the gate-4 check
        compares case-insensitively, so the token must canonicalize too."""
        signer = TimestampSigner(salt=_SALT)
        payload = {
            "email": (subscriber_email or "").strip().lower(),
            "account_id": int(account_id),
        }
        return signer.sign_object(payload)

    def decode_optout_token(token: str) -> dict:
        """Decode a signed opt-out token. Raises BadSignature on tamper.
        max_age=None — opt-out links MUST work indefinitely per the GDPR
        transactional contract (FR26). Do NOT introduce a max_age."""
        signer = TimestampSigner(salt=_SALT)
        return signer.unsign_object(token, max_age=None)
    ```
  - [x] 1.2 Use `salt=_SALT` so a leaked `SECRET_KEY`-signed token from another flow (e.g. password reset in 4.5) cannot be replayed against the opt-out endpoint. The salt is module-private; tests must use the production helper, not re-implement the signing.
  - [x] 1.3 No new dependencies — `django.core.signing` is stdlib in Django 6.x.
  - [x] 1.4 Add a `SAFENET_BASE_URL` setting to `backend/safenet_backend/settings/base.py` directly under the existing `SAFENET_SENDING_DOMAIN` block (line 144):
    ```python
    SAFENET_BASE_URL = env("SAFENET_BASE_URL", default="https://app.safenet.app")
    ```
    The default is the production domain. Local dev overrides to `http://localhost:8000` via `.env`. **Do NOT** hardcode the host in the email helpers — read from `settings.SAFENET_BASE_URL` at the point of URL assembly. **Do NOT** use Django's `HttpRequest.build_absolute_uri` — Celery tasks dispatching emails have no request object.
  - [x] 1.5 Add a third helper `build_optout_url(subscriber_email: str, account_id: int) -> str` to `optout_token.py` that wraps `build_optout_token` and returns the full URL: `f"{settings.SAFENET_BASE_URL}/optout/{token}/"`. Read `settings.SAFENET_BASE_URL` lazily at call time (not at import time — settings access at module-load violates Django convention). Strip any trailing slash on the base URL: `settings.SAFENET_BASE_URL.rstrip('/')`.
  - [x] 1.6 **Do NOT** include the company name or any other PII in the token payload. Future-you might find a use for it, but a stateless signed token is a public-by-design surface — the smaller the payload, the lower the leak surface. The `(email, account_id)` pair is sufficient.

- [x] **Task 2: Backend — Public opt-out view + URL routing** (AC: 2, 3, 7)
  - [x] 2.1 Create new module `backend/core/views/optout.py`. **No DRF** — this is a public, session-less, HTML-emitting view. Use plain Django function views with `HttpResponse(content_type="text/html")`. This sits OUTSIDE the JWT-protected DRF stack per architecture line 921-923.
  - [x] 2.2 Implement two handler functions wired through one route:
    ```python
    from django.http import HttpResponse
    from django.views.decorators.csrf import csrf_exempt
    from django.views.decorators.http import require_http_methods
    from django.db import IntegrityError
    from django.core.signing import BadSignature

    from core.models.account import Account
    from core.models.notification import NotificationOptOut
    from core.models.subscriber import Subscriber
    from core.services.audit import write_audit_event
    from core.services.optout_token import decode_optout_token

    logger = logging.getLogger(__name__)

    @csrf_exempt
    @require_http_methods(["GET", "POST"])
    def optout_view(request, token: str):
        # Decode token (re-decoded on POST too — never trust form-state)
        try:
            payload = decode_optout_token(token)
        except BadSignature as exc:
            logger.warning("[optout_view] INVALID_TOKEN exception_type=%s", type(exc).__name__)
            return HttpResponse(_render_invalid_page(), content_type="text/html", status=200)

        email = payload["email"]
        account_id = payload["account_id"]

        try:
            account = Account.objects.get(pk=account_id)
        except Account.DoesNotExist:
            logger.warning("[optout_view] ACCOUNT_NOT_FOUND account_id=%s", account_id)
            return HttpResponse(_render_invalid_page(), content_type="text/html", status=200)

        company = account.company_name or "this service"

        if request.method == "GET":
            logger.info("[optout_view] GET token_valid=True account_id=%s", account_id)
            return HttpResponse(
                _render_confirm_page(company=company, action_url=request.path),
                content_type="text/html", status=200,
            )

        # POST — commit the opt-out
        already_existed = False
        created_row = None
        try:
            created_row = NotificationOptOut.objects.create(
                account=account,
                subscriber_email=email,
            )
        except IntegrityError:
            already_existed = True

        if not already_existed:
            # Best-effort subscriber lookup for audit (may be None — opt-out
            # works even if SafeNet has no Subscriber row yet, since the
            # NotificationOptOut row is the source of truth).
            subscriber = (
                Subscriber.objects
                .for_account(account_id)
                .filter(email__iexact=email)
                .first()
            )
            write_audit_event(
                subscriber=str(subscriber.id) if subscriber else None,
                actor="subscriber",
                action="notification_opted_out",
                outcome="success",
                metadata={
                    "subscriber_email": email,
                    "account_id": account_id,
                    "company_name": account.company_name,
                },
                account=account,
            )

        logger.info(
            "[optout_view] POST opted_out account_id=%s already_existed=%s",
            account_id, already_existed,
        )

        return HttpResponse(
            _render_success_page(company=company),
            content_type="text/html", status=200,
        )
    ```
  - [x] 2.3 Implement three private HTML renderers in the same module:
    - `_render_confirm_page(company: str, action_url: str) -> str` — uses the **same `_render_email_shell` import from `core.services.email`** for visual consistency. Inner HTML: brand header (already in shell as `<h2>`), one paragraph "Confirm you'd like to unsubscribe from payment notifications for {escaped_company}.", and a `<form method="POST" action="{escaped_action_url}"><button type="submit" style="...">Unsubscribe</button></form>`. Apply `html.escape()` to `company` and `action_url`.
    - `_render_success_page(company: str) -> str` — same shell. Inner HTML: one paragraph reading verbatim "You've been unsubscribed from payment notifications for {escaped_company}."
    - `_render_invalid_page() -> str` — same shell with `escaped_company=""` so the brand header is empty (visually neutral). Inner HTML: "This unsubscribe link is no longer valid. If you continue to receive emails, contact the sender directly." — generic, never confirms or denies an email/account exists.
  - [x] 2.4 Add a `<meta name="robots" content="noindex,nofollow">` to the `_render_email_shell` `<head>` block. This is **safe** for emails (most clients ignore the tag) and required for the public opt-out pages. Verify the existing 4.1 / 4.3 escape tests still pass (the shell signature does not change).
  - [x] 2.5 Add the route to `backend/safenet_backend/urls.py` **at the project URLConf level**, NOT in `core/urls.py`. The path is `path("optout/<str:token>/", optout_view, name="notification_optout")` — sits next to `path("api/", include("core.urls"))`. **Critical:** the path is intentionally `optout/`, NOT `api/v1/optout/` — it is not part of the JSON API surface, has no JWT layer, and lives at the top-level project route (matches architecture.md line 921-923).
  - [x] 2.6 The view module is `core/views/optout.py` — same package as the other views. The renderer helpers stay private to the module (`_render_*` — leading underscore). Import `_render_email_shell` from `core.services.email` (it is private-by-convention but already exported via the existing 4.3 import pattern; the import is a one-liner and the shell is the visual single source of truth). If a code reviewer flags the underscore-import, the alternative is to move `_render_email_shell` to a shared module — that is **out of scope for this story**; defer.
  - [x] 2.7 Add `actor="subscriber"` to the audit grammar. Update `core/services/audit.py` docstring (line 36): change `actor: One of "engine", "operator", "client"` → `actor: One of "engine", "operator", "client", "subscriber"`. Update `architecture.md` only if convenient — the docstring is the source of truth code-side. **Do NOT** add a CHECK constraint to `AuditLog.actor` — it's a free-form string in the existing schema; introducing a constraint is a separate epic.

- [x] **Task 3: Backend — Replace placeholder URL in all three send paths** (AC: 1)
  - [x] 3.1 In `backend/core/services/email.py`, replace each of the three placeholder lines (279, 337, 388) with a call to `build_optout_url`:
    ```python
    from core.services.optout_token import build_optout_url

    # at line 279, 337, 388:
    opt_out_url = build_optout_url(
        subscriber_email=(subscriber.email or "").strip().lower(),
        account_id=account.id,
    )
    ```
    **Critical:** lower-case + strip the email **before** calling `build_optout_url` so the signed payload matches what Gate 4's `subscriber_email__iexact=subscriber.email.strip()` lookup will find at suppress time. The signing function in 1.1 also lower-cases defensively, but doing it at the call site makes the contract explicit.
  - [x] 3.2 Place the `from core.services.optout_token import build_optout_url` import at module top alongside the other `core.services` imports (line 14-20 region). Do **NOT** import inside the function body — that pattern only exists in `recovery.py` to break the import cycle with `tasks/notifications.py`; the optout module has no such cycle.
  - [x] 3.3 In `backend/core/views/account.py` `notification_preview` (line 283), replace the placeholder URL with a **preview token** that decodes successfully but is never used to opt out a real subscriber:
    ```python
    # account.py:283 — currently: opt_out_url = "https://app.safenet.app/notifications/opt-out"
    from core.services.optout_token import build_optout_url
    opt_out_url = build_optout_url(
        subscriber_email="preview@example.com",
        account_id=account.id,
    )
    ```
    The preview email shows the real token format. If the founder clicks it (highly unlikely on their own preview), the GET endpoint shows the confirm page; clicking POST creates a `NotificationOptOut(subscriber_email="preview@example.com", account=their_account)` row — harmless because no real subscriber has that email. Do **NOT** add a `?preview=1` flag to the URL — the entire point is the preview is byte-equivalent to a real email so founders see exactly what subscribers see.
  - [x] 3.4 Verify (by running the existing 4.1 / 4.2 / 4.3 test suite) that no test asserts the **exact** placeholder string `"https://app.safenet.app/notifications/opt-out"` — if it does, rewrite the assertion to assert the URL *shape* instead: `assert "/optout/" in html_body and html_body.startswith(...)` style. Specifically check `test_email.py` lines 310 and 515 (identified by grep) — adjust if needed.

- [x] **Task 4: Backend — Tests for the token helper** (AC: 1)
  - [x] 4.1 Create `backend/core/tests/test_services/test_optout_token.py`:
    - `test_round_trip` — `build_optout_token("a@b.com", 7)` → `decode_optout_token(token)` returns `{"email": "a@b.com", "account_id": 7}`.
    - `test_email_canonicalized` — `build_optout_token("  A@B.COM  ", 7)` → decoded payload has `email == "a@b.com"`.
    - `test_account_id_coerced_to_int` — `build_optout_token("a@b.com", "7")` (string) → decoded `account_id == 7` (int).
    - `test_tampered_token_raises_bad_signature` — flip a single character in the token → `pytest.raises(BadSignature)`.
    - `test_token_from_different_salt_rejected` — manually sign with a different salt via `TimestampSigner(salt="other")`, attempt to decode → `pytest.raises(BadSignature)`.
    - `test_build_optout_url_uses_settings` — `with override_settings(SAFENET_BASE_URL="http://localhost:8000")`, assert URL starts with `"http://localhost:8000/optout/"` and contains a non-empty token segment.
    - `test_build_optout_url_strips_trailing_slash` — `override_settings(SAFENET_BASE_URL="http://x/")`, assert URL has no double slash before `/optout/`.
    - `test_no_max_age_enforced` — sign a token, monkeypatch system clock forward 365 days (use `freezegun` if installed; otherwise patch `time.time`), assert `decode_optout_token` still succeeds. **If freezegun is not installed**: the unsign call uses `max_age=None` so the test is structurally guaranteed; assert that `decode_optout_token`'s call site passes `max_age=None` (string-search the source) instead of running a clock test.
  - [x] 4.2 Reuse the existing `pytest` + `pytest-django` setup. No fixtures from `conftest.py` are needed — the helper is pure-Python.

- [x] **Task 5: Backend — Tests for the public optout view** (AC: 2, 3, 7)
  - [x] 5.1 Create `backend/core/tests/test_api/test_optout.py` (placed in `test_api/` even though it's not a JSON API — keeps view-level tests in one folder; the alternative `test_views/` does not yet exist and creating it for one file would be churn). **Use Django's `Client`, NOT DRF's `APIClient`** — the endpoint returns HTML, not JSON.
  - [x] 5.2 Test list (mirror the 4.3 task-test scaffolding):
    - `test_get_returns_confirm_page_for_valid_token` — build a token for a real account, GET the URL, assert 200, assert `b"Confirm" in response.content`, assert `b"<form method=\"POST\"" in response.content`.
    - `test_get_does_not_create_optout_row` — same as above; assert `NotificationOptOut.objects.count() == 0` after the GET (proves prefetch-protection — Gmail / Outlook scanners hitting the link do NOT auto-opt-out).
    - `test_post_creates_optout_row` — POST the URL with a valid token, assert 200, assert `NotificationOptOut.objects.filter(account=account, subscriber_email="sub@x.com").exists()`.
    - `test_post_writes_audit_event` — assert `AuditLog.objects.filter(action="notification_opted_out", actor="subscriber", account=account).count() == 1`. Inspect `metadata` for `subscriber_email`, `account_id`, `company_name`.
    - `test_post_idempotent_when_row_already_exists` — pre-create the `NotificationOptOut` row, POST the URL, assert 200, assert `NotificationOptOut.objects.count() == 1` (no duplicate), assert **no new audit row** is written (`AuditLog.objects.filter(action="notification_opted_out").count() == 0` — pre-existing rows count zero because we created the opt-out directly, not via the view).
    - `test_post_renders_success_page` — assert `b"unsubscribed" in response.content.lower()` and the company name appears.
    - `test_invalid_token_returns_generic_message` — GET `/optout/garbage/`, assert 200, assert `b"no longer valid" in response.content`, assert no row created and no audit event.
    - `test_invalid_token_does_not_leak_info` — try a token whose `account_id=99999` (does not exist), assert 200 with the same generic message — must not differentiate between "bad signature" and "account deleted".
    - `test_get_tampered_token_returns_generic` — flip one char of a valid token, GET → 200, generic message, no DB writes.
    - `test_post_with_no_subscriber_row_still_audits` — opt out an email with no matching `Subscriber` row in any account; assert the audit row has `subscriber_id=None` and `metadata.subscriber_email` populated.
    - `test_post_finds_subscriber_for_audit` — pre-create a `Subscriber(email="sub@x.com")` for the same account; POST; assert audit row's `subscriber_id` matches the subscriber's UUID (string-form).
    - `test_csrf_exempt_post_works_without_cookie` — POST without setting a CSRF cookie; assert 200 (verifies `@csrf_exempt`). Default Django test client doesn't send CSRF tokens, so a normal POST already exercises this; add an explicit assertion that `response.status_code == 200`.
    - `test_email_lookup_case_insensitive` — sign token with `subscriber_email="A@B.com"` (mixed case); POST; assert the created `NotificationOptOut.subscriber_email` is the canonicalized lower-cased form.
    - `test_response_includes_robots_meta` — assert `b'noindex,nofollow' in response.content` for both the confirm and success pages.
  - [x] 5.3 Use a `mid_account` fixture mirroring the existing pattern in `test_tasks/test_notifications.py:25-39` and `test_models/test_notification.py:25-32`. Include `company_name="TestCo"` so renderers display a real brand string.
  - [x] 5.4 Don't write a separate XSS test class — the existing 4.3 escape tests cover `_render_email_shell`. **However**, add one regression: `test_company_name_escaped_in_confirm_page` — set `account.company_name = "<script>alert(1)</script>"`, GET the confirm URL, assert the literal `<script>` tag is **not** present in the response body, assert `&lt;script&gt;` IS present. This guards against a "rendered straight into HTML" regression in any of the three private renderers.

- [x] **Task 6: Backend — Integration tests proving Gate 4 suppresses opted-out subscribers** (AC: 4, 5, 6)
  - [x] 6.1 Extend `backend/core/tests/test_tasks/test_notifications.py`. The existing `TestSendFailureNotification.test_opt_out_suppressed` case at notifications.py:64-69 already tests Gate 4 for the failure-notice path. The 4.3 changes added the same case for `final_notice` and `recovery_confirmation`. **Verify** all three exist; if any are missing, add them now to `TestSendFinalNotice` and `TestSendRecoveryConfirmation`. The new assertion in this story:
    - `test_opt_out_check_uses_canonical_email` — pre-create `NotificationOptOut(subscriber_email="sub@x.com")` (lower-case, no whitespace), set `subscriber.email = "  Sub@X.COM  "` (mixed case, trailing whitespace), call `send_failure_notification.delay(failure_id)` → assert the gate fires (suppressed log + audit). This locks in the **canonicalization contract** between Task 3.1 (lower-case-strip at sign time) and notifications.py:64 (`subscriber_email__iexact=subscriber.email.strip()`).
  - [x] 6.2 Add `test_optout_scoped_per_account_pair`:
    - Create two accounts `A` and `B` with the same `subscriber.email = "shared@x.com"`.
    - Create a `NotificationOptOut(account=A, subscriber_email="shared@x.com")`.
    - Trigger `send_failure_notification` for the failure on account `A` → assert suppressed.
    - Trigger `send_failure_notification` for the failure on account `B` → assert NOT suppressed (the email is sent or at least Gate 4 does not fire).
    - This regression test is **non-negotiable** — FR27 / AC 6 is a top concern: a SafeNet-wide opt-out would create a cross-tenant data leak. Place it in `test_notifications.py::TestNotificationOptOutTenantScoping`.
  - [x] 6.3 Add `test_optout_does_not_affect_other_email_types_for_same_pair`:
    - This is **the inverse** of AC 4. Verify that if a subscriber opts out, **all three** email types are suppressed for the (subscriber_email, account) pair, not just `failure_notice`. Add a parametrized test across `email_type ∈ {"failure_notice", "final_notice", "recovery_confirmation"}`. For each, the existing Gate 4 must fire and write the corresponding `NotificationLog(status="suppressed", email_type=<type>)` row. This makes AC 4's "every notification type" claim machine-verifiable.

- [x] **Task 7: Backend — End-to-end test: opt-out flow** (AC: 1, 2, 3, 4)
  - [x] 7.1 Create `backend/core/tests/test_api/test_optout_e2e.py` (single integration test that proves the full flow):
    - **Step 1:** Account with `tier=Mid + DPA + engine_mode=autopilot + company_name="TestCo"`. Subscriber with `email="sub@x.com"`. SubscriberFailure on `card_expired`.
    - **Step 2:** Call `send_notification_email(subscriber, failure, account)` directly (mock `resend.Emails.send`). Capture the `html` body that would have been sent. Assert it contains a `/optout/` URL.
    - **Step 3:** Extract the token from the captured HTML using a regex (`r"/optout/([^/\"]+)/"`).
    - **Step 4:** Use Django's test `Client.get(f"/optout/{token}/")` → 200, confirm page.
    - **Step 5:** `Client.post(f"/optout/{token}/")` → 200, success page. Assert `NotificationOptOut(account=account, subscriber_email="sub@x.com")` row exists.
    - **Step 6:** Re-call `send_notification_email(subscriber, failure_2, account)` (a second failure on the same subscriber). Assert it raises `SkipNotification` is **NOT** the right path here — the gate sequence runs in the **task** not the helper. Instead call `send_failure_notification.delay(failure_2.id)` (or `send_failure_notification.run(failure_2.id)` for synchronous test) and assert the suppressed `NotificationLog` row was created with `metadata.reason="opt_out"`.
    - This single test exercises every layer: signing → email rendering → URL extraction → public view → opt-out persistence → gate suppression.
  - [x] 7.2 Mock `resend.Emails.send` to return a fixed `{"id": "msg_e2e"}` so step 2 doesn't try to hit the real Resend API. The existing `_resend_configured` autouse fixture handles `RESEND_API_KEY`.

- [x] **Task 8: Backend — Documentation alignment** (AC: 6, 7)
  - [x] 8.1 In `core/services/audit.py` docstring, line 25-26: extend the `actor` enum docstring to include `subscriber`. One-line edit. **Do NOT** introduce a constants module — the audit grammar lives in docstrings + tests today; this story is not the moment to refactor that pattern.
  - [x] 8.2 In `core/views/optout.py` module docstring (top of file), document:
    - "Public, unauthenticated, session-less subscriber-facing endpoint per architecture.md line 921-923."
    - "Gate 4 in tasks/notifications.py is the suppression source of truth — this view's only side-effect is creating a `NotificationOptOut` row."
    - "Tokens are stateless (Django signing, no DB) and never expire — FR26 / GDPR transactional contract."
    - "@csrf_exempt is intentional: the signed token in the URL is the proof-of-intent. There is no session to attack."
  - [x] 8.3 No new `.env.example` entry needed — the new `SAFENET_BASE_URL` setting has a sensible default (`https://app.safenet.app`). However, **add** the variable to `backend/.env.example` with `SAFENET_BASE_URL=http://localhost:8000` so local devs running `docker compose up` get a URL that resolves to their local backend. The default in `settings/base.py` stays as the production value.
  - [x] 8.4 No frontend changes. The opt-out endpoint serves its own HTML; the frontend Next.js stack is untouched in this story. Story 4.5 (password reset) introduces the first password-reset frontend route, not this one.

## Dev Notes

### Architecture Compliance

- **Public endpoint isolation.** Per architecture.md line 921-923, `views/optout.py` is the **public, JWT-bypassed** opt-out endpoint. It lives at `/optout/{token}/` (project URLConf level), NOT under `/api/v1/`. **Do NOT** wire it into `core/urls.py` or DRF — it returns HTML, not JSON, and has no JWT layer.
- **Stateless signed tokens.** Django's `signing.TimestampSigner.sign_object` is the production-grade pattern for this exact use case. No new DB rows, no token storage. The signing key is `SECRET_KEY` (already required by Django and present in all environments). Salting via `_SALT="safenet.notifications.optout"` prevents cross-flow token replay. Same family of helpers used by `PasswordResetTokenGenerator` (which Story 4.5 will use for password resets).
- **`max_age=None` is intentional.** Opt-out links must work indefinitely — a subscriber may keep an old email for years and still need to be able to opt out. Per FR26 / GDPR, the contractual obligation has no expiration. Do NOT pass a `max_age` argument.
- **Email canonicalization at sign time.** `subscriber_email` is lower-cased + stripped before signing (Task 1.1) AND before being passed into `build_optout_url` from email.py (Task 3.1). Gate 4's lookup uses `subscriber_email__iexact=subscriber.email.strip()` (notifications.py:64) — both ends MUST agree on canonicalization or the gate fails to suppress an opt-out subscriber. Tests in Task 6.1 lock this contract.
- **Audit grammar extension: `actor="subscriber"`.** This is the first end-customer-side actor in the audit log (existing values: `engine`, `operator`, `client`). `subscriber` is appropriate because the action originates from the subscriber's intent, not from a SafeNet-side actor. Update `core/services/audit.py` docstring; do NOT add a CHECK constraint (the field is `models.CharField(max_length=20)` today and we are not introducing schema constraints in this story).
- **Inline HTML over Django templates.** Same MVP rationale as Story 4.1 emails — the codebase has zero Django templates today; introducing a template directory for two trivial pages (confirm + success + invalid) is unjustified surface area. `_render_email_shell` is reused for visual consistency. If this approach proves brittle when more public pages are added (Story 4.5 password reset is a candidate), the refactor is explicit and post-MVP.
- **No CSRF on POST.** The signed token in the URL IS the proof-of-intent. Adding CSRF would require setting cookies on the GET, which adds session-middleware coupling for zero security gain (the token is the auth). `@csrf_exempt` is correct here. The architecture docstring at 921-923 explicitly designates this endpoint as outside the JWT/session stack.
- **`@require_http_methods(["GET", "POST"])`** ensures other methods (PUT/DELETE/PATCH) return 405. The view function dispatches on `request.method`.
- **Gate 4 is the source of truth for suppression.** The view's only side-effect is creating a `NotificationOptOut` row. The gate at notifications.py:64-69 (existing) does ALL the suppression work — for all three email types. This story does NOT modify `_passes_gates`; it only verifies the pre-existing behavior with new tests.

### Existing Code to Reuse (DO NOT reinvent)

| What | Where | Usage |
|------|-------|-------|
| `NotificationOptOut` model + `unique_opt_out_per_account` constraint | `backend/core/models/notification.py:55-67` | Already exists with `(subscriber_email, account)` unique. **No new migration required.** The IntegrityError on duplicate-create is the idempotency mechanism. |
| `_passes_gates` Gate 4 (opt-out check) | `backend/core/tasks/notifications.py:63-69` | Already implements per-(email, account) suppression for all 3 email types. **Do NOT modify.** Verify with new tests only. |
| `_log_suppression(reason="opt_out", email_type=<type>)` | `backend/core/tasks/notifications.py:376-416` | Generalized in 4.3 — already accepts `email_type`. The existing call sites pass `reason="opt_out"` already. |
| `_render_email_shell` | `backend/core/services/email.py:74-94` | Use for the public opt-out HTML pages — visual single source of truth. Add `<meta name="robots">` per Task 2.4. |
| `write_audit_event` | `backend/core/services/audit.py:11-50` | Sole audit write path. New `actor="subscriber"` value extends the documented enum but does not change the call signature. |
| `TimestampSigner` (Django stdlib) | `django.core.signing` | Stateless signed tokens. No DB row, no migration, no new dependency. Same family used by Django's `PasswordResetTokenGenerator`. |
| `Subscriber.objects.for_account(account_id).filter(email__iexact=...)` | `backend/core/models/subscriber.py` (TenantScopedModel) | Best-effort lookup at audit-write time. May return None — that is acceptable; the opt-out row stands on its own. |
| `Account.objects.get(pk=account_id)` | `backend/core/models/account.py:31` | Account is **not** a TenantScopedModel (it IS the tenant). `objects.get(pk=...)` is correct here. |
| `mid_account`, `subscriber`, `failure` fixtures | `backend/core/tests/test_tasks/test_notifications.py:25-62` and `test_models/test_notification.py:25-54` | Reuse for new test files. Move to `conftest.py` only if duplication exceeds 2 files — for 4.4 specifically, copy the fixture into the new test files (matches 4.3 pattern). |
| `_resend_configured`, `_fernet_key` autouse fixtures | `backend/core/tests/test_services/test_email.py` and `test_tasks/test_notifications.py` | Mock the Resend SDK setup for the e2e test (Task 7.1). |
| `csrf_exempt`, `require_http_methods` | `django.views.decorators.csrf` / `.http` | Stdlib decorators. No new dependency. |

### What NOT to Do

- Do **NOT** add a `JWT`-protected `/api/v1/optout/...` endpoint. The architecture spec is explicit: this is **public, session-less, JWT-bypassed**. The token in the URL is the only auth.
- Do **NOT** add CSRF protection. The signed token is the proof-of-intent. Adding CSRF requires session cookies, contradicts the session-less design, and provides zero additional security (a forged unsubscribe POST without a valid token is rejected at decode time).
- Do **NOT** add a max_age to `decode_optout_token`. Opt-out links must work indefinitely per the GDPR transactional contract. A subscriber holding a 5-year-old email must still be able to opt out.
- Do **NOT** introduce Django templates. Two trivial public HTML pages do not justify a template engine. Reuse `_render_email_shell` for visual consistency.
- Do **NOT** modify `_passes_gates` in `tasks/notifications.py`. Gate 4 already works for all three email types as of Story 4.3. The only modifications in this story are: (a) wiring real opt-out URLs into the email-builders, (b) adding the public view + token helper, (c) adding the `actor="subscriber"` audit grammar, (d) adding tests.
- Do **NOT** introduce a "global opt-out" or "opt-out from all SafeNet emails across all accounts." FR27 explicitly scopes opt-out to (subscriber_email, account). A subscriber who opts out from Brand A still receives emails from Brand B if they are also a customer of Brand B. AC 6 / Task 6.2 are non-negotiable regression guards.
- Do **NOT** integrate with the client's own marketing-opt-out lists. SafeNet emails are transactional under contractual necessity; a marketing opt-out from the client's CRM does not suppress SafeNet emails. PRD line 504 is explicit.
- Do **NOT** add a `?preview=1` flag or any other branch in `notification_preview` to differentiate between preview-rendered HTML and real-email HTML. The preview must be byte-equivalent. Founders must see exactly what subscribers see — including the live (but harmless) opt-out token.
- Do **NOT** auto-opt-out on GET. The GET is a confirmation gate. POST commits. This defends against email-scanner / Gmail / Outlook link-prefetching auto-creating opt-outs (a real-world incident pattern documented in OWASP and email-platform docs).
- Do **NOT** encode the company name, subscriber UUID, or any other PII into the token. Stateless signed tokens are public-by-design; minimize the leak surface to `(email, account_id)` only.
- Do **NOT** add rate limiting on the optout endpoint at MVP. The unsign path is microsecond-cheap, never touches PostgreSQL, and the abuse model (someone minting random tokens) is bounded by the SECRET_KEY signing strength. Document as a deferred follow-up.
- Do **NOT** introduce `RFC 8058` `List-Unsubscribe-Post` headers in the Resend payload. Out of scope for MVP — the visible opt-out link satisfies FR26 / FR27. Add as a follow-up story when ready to support one-click email-client native unsubscribe.
- Do **NOT** swallow the `BadSignature` exception silently. Log at WARNING level with `exception_type` only — never log the raw token (Sentry / log-aggregator leak risk).
- Do **NOT** add the `optout_view` function or its renderers to a `views/__init__.py` re-export. The route registration in `urls.py` is the only consumer.

### API Contracts

This story introduces **one** new public endpoint and modifies **zero** existing API contracts.

- `GET /optout/<str:token>/` → `200 text/html` (confirm page) | `200 text/html` (invalid-token generic page)
- `POST /optout/<str:token>/` → `200 text/html` (success page, idempotent) | `200 text/html` (invalid-token generic page)

The existing JSON API endpoints under `/api/v1/...` are unchanged. The notification_preview endpoint (`/api/v1/account/notification-preview/`) renders a real-format opt-out URL but its response shape is unchanged.

**Why GET-then-POST instead of one-click GET?** Email scanners (Gmail, Outlook 365, Apple Mail Privacy Protection, corporate URL-rewriting proxies like Proofpoint and Mimecast) automatically fetch every link in every email to scan for malware. A one-click GET would auto-opt-out every recipient whose mail provider scans links. The GET-then-POST pattern is the standard defense.

### Tenant Isolation

- `NotificationOptOut` is `TenantScopedModel` — every row has `account_id`. The view's `Account.objects.get(pk=account_id)` resolves the account from the signed token; the row is then created with that account FK. Cross-tenant leakage is **physically impossible** at the model level.
- The audit row written from the optout view uses the same `write_audit_event(account=account, ...)` pattern as every other engine action — `account_id` is the scoping anchor.
- Gate 4 in `_passes_gates` filters by `account=account` (notifications.py:66) — a subscriber who opted out from Brand A cannot suppress notifications from Brand B for the same email address. Task 6.2 is the regression test.
- The token payload contains `account_id` directly (not derived from a secondary lookup) — this means a leaked token cannot be replayed against a different account by tampering with a parameter; tampering invalidates the signature.

### Audit Trail (MUST use single write path)

```python
# Successful opt-out (POST)
write_audit_event(
    subscriber=str(subscriber.id) if subscriber else None,  # best-effort lookup
    actor="subscriber",                                      # NEW grammar value
    action="notification_opted_out",
    outcome="success",
    metadata={
        "subscriber_email": email,    # canonical lower-cased
        "account_id": account_id,     # int
        "company_name": account.company_name,
    },
    account=account,
)

# NO audit row on:
#   - GET (read-only)
#   - duplicate POST (idempotent — the row already exists, no new state)
#   - invalid token (not a state-changing event; logged at WARNING, not audited)
```

The grammar is `notification_opted_out` (past-tense verb, snake_case, parallel to existing `notification_sent` / `notification_suppressed` / `notification_failed`). This single action name covers the entire opt-out lifecycle from the audit-trail perspective. Operator queries can filter by `action="notification_opted_out"` to surface every opt-out across all accounts.

### Gate Check Order (unchanged from Story 4.3)

Identical to Story 4.3 — this story does NOT modify the gate sequence:

1. `is_engine_active(account)` — Mid/Pro tier + DPA + engine mode set
2. `subscriber.email` non-blank (after strip)
3. `subscriber.excluded_from_automation` is `False`
4. **`NotificationOptOut` exists for `(subscriber_email__iexact, account)`** — this is what Story 4.4 wires up the user-facing surface for
5. Duplicate `NotificationLog` exists for `(failure, email_type, status="sent", account)`
6. (`final_notice` only) `subscriber.status == STATUS_ACTIVE` (Story 4.3 patch)

The opt-out check (Gate 4) **must run before any send**. This is a property of `_passes_gates` (notifications.py:31-94), enforced by the existing 4.1/4.2/4.3 task tests for each email type. Task 6.3 adds a parametrized test that locks Gate 4's coverage of all three email types in one place.

### GDPR Classification (FR27 / AC 6)

SafeNet emails are classified as **transactional under contractual necessity**, not marketing. The implication for opt-out scope:

- A subscriber opt-out via SafeNet's link suppresses **SafeNet-dispatched emails for that (subscriber_email, account_id) pair only**.
- A standard marketing-opt-out from the client's own CRM (e.g. unsubscribing from Brand A's product newsletter via Mailchimp) does **NOT** propagate to SafeNet. SafeNet has no inbound integration with client marketing platforms.
- A subscriber who opts out from Brand A's payment notifications can still legitimately receive Brand A's marketing emails (those are governed by the client's own CRM, not SafeNet).
- A subscriber who is also a customer of Brand B will continue to receive SafeNet emails from Brand B even after opting out from Brand A — the (subscriber_email, account_id) scoping is fundamental.

This is the operator-facing answer to "why is this user still getting SafeNet emails after they opted out?" — check which (email, account_id) pair they opted out FROM versus which one is sending now.

### Project Structure Notes

**New files to create:**
```
backend/core/services/optout_token.py            # build_optout_token, decode_optout_token, build_optout_url
backend/core/views/optout.py                     # optout_view + private renderers
backend/core/tests/test_services/test_optout_token.py   # 8 helper tests
backend/core/tests/test_api/test_optout.py              # ~14 view tests
backend/core/tests/test_api/test_optout_e2e.py          # 1 end-to-end test
```

**Files to modify:**
```
backend/safenet_backend/urls.py              # +path("optout/<str:token>/", optout_view, ...)
backend/safenet_backend/settings/base.py     # +SAFENET_BASE_URL setting
backend/.env.example                         # +SAFENET_BASE_URL=http://localhost:8000
backend/core/services/email.py               # 3× placeholder URL → build_optout_url; +<meta robots> in _render_email_shell
backend/core/services/audit.py               # docstring: extend actor enum to include "subscriber"
backend/core/views/account.py                # notification_preview: placeholder URL → build_optout_url with preview email
backend/core/tests/test_tasks/test_notifications.py    # +test_opt_out_check_uses_canonical_email; +TestNotificationOptOutTenantScoping; +parametrized 3-email-type opt-out test
```

**Migrations:** None. `NotificationOptOut` model + constraint already exist (migration 0012). The `unique_opt_out_per_account` constraint is the idempotency source of truth.

**No frontend changes.** All public-facing surface lives at `/optout/{token}/` on the Django backend.

**No new dependencies.** Everything uses Django stdlib (`signing`, `views.decorators.csrf`, `views.decorators.http`, `http.HttpResponse`).

### Dependencies

- **Upstream:** Story 4.1 done (Resend, `NotificationLog`, `NotificationOptOut`, `send_failure_notification`, gate sequence). Story 4.2 done (`Account.notification_tone`, `email_templates.py`, notification preview endpoint). Story 4.3 done (`send_final_notice`, `send_recovery_confirmation`, generalized `_log_suppression`/`_record_failure`, `_render_email_shell` extracted, partial unique constraint on `NotificationLog`). Migration 0014 is the latest.
- **Downstream:** Story 4.5 (password reset) will use a similar `signing.TimestampSigner` pattern but with `max_age=3600` (1-hour expiry per Story 4.5 spec). The two flows do NOT share salts or token formats — Task 1.2 enforces this isolation.
- **Open patches inherited:**
  - **`customer_update_url` `javascript:` scheme validation (4.3 deferred):** still deferred. Out of scope here. The opt-out URL is constructed by `build_optout_url` and is fully controlled by SafeNet — no untrusted input flows in.
  - **`NotificationLog.email_type` no `choices=` constraint (4.3 deferred):** still deferred. The opt-out flow does not write `NotificationLog` rows directly; Gate 4's `_log_suppression` already passes `email_type=<known-good>`.
  - **`_record_failure` swallows exceptions silently (4.3 deferred):** still deferred. The opt-out view does not use `_record_failure`.

### Testing Standards

- **Backend:** pytest. Use Django's `Client` (NOT DRF's `APIClient`) for the optout endpoint — it returns HTML, not JSON. Use `pytest-django` `client` fixture: `def test_x(client, ...)`. For DB, use `@pytest.mark.django_db` (matches all existing test classes).
- **Mocking:** Mock `resend.Emails.send` with `@patch("resend.Emails.send")` for the e2e test (Task 7.1). The optout view itself has no Resend dependency.
- **Fixtures:** Reuse `mid_account` (Mid tier + DPA + engine_mode + company_name + StripeConnection), `subscriber_with_email`, `failure` from existing `test_tasks/test_notifications.py` — copy fixtures into new test files (matches 4.3 pattern; `conftest.py` consolidation is not part of this story).
- **Coverage target:** every AC has at least one direct test. The token helper (Task 1) has its own pure-Python test file (Task 4). The view (Task 2) has its own Django-Client test file (Task 5). The Gate 4 / suppression / tenant-scoping behavior (AC 4) has tests in `test_notifications.py` (Task 6). The e2e flow has a single integration test (Task 7).
- **Critical regression guards:**
  1. The existing 4.1 / 4.2 / 4.3 escape tests (`test_email_html_escapes_company_name` and friends) MUST still pass after `_render_email_shell` gains the `<meta robots>` tag. The shell signature does not change, only the content inside `<head>`.
  2. The 4.3 `TestSendFailureNotification.test_opt_out_suppressed` and the parallel cases in `TestSendFinalNotice` and `TestSendRecoveryConfirmation` MUST still pass after the placeholder URL is replaced. Those tests pre-create a `NotificationOptOut` row directly and assert Gate 4 fires — they do not depend on the URL value.
  3. The 4.2 `test_notification_preview_renders_full_email_shape` (or equivalent) MUST still pass after the preview URL becomes a real signed token instead of a placeholder string. If the test asserts the literal placeholder, change the assertion to a shape check (regex `r"/optout/[^/]+/"`).
- **Manual verification:** Local end-to-end:
  1. `docker compose up`
  2. `manage.py shell` — create `Subscriber(account=A, email="me@example.com")`, `SubscriberFailure(...)`. Trigger `send_failure_notification.delay(failure_id)` (mock Resend or set a real key for staging).
  3. Inspect Resend dashboard or local SMTP capture: confirm opt-out URL has shape `http://localhost:8000/optout/<token>/`.
  4. Click the link in the rendered email body or paste in browser → confirm page renders with company name + "Unsubscribe" button.
  5. Click "Unsubscribe" → success page renders.
  6. `manage.py shell` — verify `NotificationOptOut.objects.filter(subscriber_email="me@example.com").exists()` returns True.
  7. Trigger another `send_failure_notification.delay(failure_id_2)` for the same subscriber → verify a `NotificationLog(status="suppressed", metadata__reason="opt_out")` row was written, no email was sent.
  8. Document Steps 1-7 in Completion Notes.

### Previous Story Intelligence (4.3)

- **`_render_email_shell` already exists** (4.3 Task 2.3). Reuse for the public opt-out HTML pages. The shell signature is `(escaped_company: str, inner_html: str) -> str`. Pass `html.escape(company_name)` as the first argument. **Do not pass raw company_name** — the shell expects already-escaped input (4.3 Task 2.3 contract).
- **Footer-double-escape fix landed in 4.3.** Pattern: pass raw `company_name` once, escape exactly once at the f-string boundary. The opt-out view's renderers MUST follow this pattern. Test with `company_name="<script>alert(1)</script>"` (Task 5.4).
- **Gate 4 already supports all three email types** (4.3 generalized `_passes_gates`). This story does NOT modify `_passes_gates`; it only verifies via Task 6.3.
- **`_log_suppression(reason="opt_out", email_type=<type>)`** already writes `NotificationLog` and audit rows correctly across the 3 types — verified in 4.3 review patches.
- **`actor` enum extension is novel.** The existing values `engine | operator | client` did not have a subscriber-side actor. Story 4.4 introduces `subscriber`. Update `audit.py` docstring (Task 8.1) — leaving the enum implicit risks future code reviewers reverting the value as a typo.
- **Idempotency via DB constraint, not pre-check** (4.3 design): `NotificationOptOut.unique_opt_out_per_account` is the source of truth. The view does `try: create() except IntegrityError: pass` — no `if exists()` pre-check (TOCTOU-vulnerable per 4.3 review).
- **No frontend changes** matches 4.3 (engine + email-template only). Story 4.5 (password reset) will be the first frontend-touching story since 4.2.
- **`from collections.abc import Callable` (4.2 patch)** is the canonical import. If any new module adds Callable typing, follow the same convention.
- **`override_settings`** for tests that depend on `SAFENET_BASE_URL` (Task 4.1's `test_build_optout_url_uses_settings`). Pattern: `from django.test import override_settings`; decorate or use as context manager.

### Git Intelligence (last 5 commits, 2026-04-15 → 2026-04-27)

```
a23988e  Story 4.3: final notice & recovery confirmation emails + 9 review patches
1c7a131  Merge pull request #1 — review/3-2-autopilot-recovery-engine
f516e92  Story 4.2 review: apply 14 patches from adversarial code review
2ed02f5  Part2  (4.2 implementation, mid-stream)
9e704ea  Story 4.1 review: apply 21 patches from adversarial code review
```

Recent change patterns observed in the codebase:
- **Patch application is a separate commit** from initial implementation (4.1, 4.2, 4.3 all follow this rhythm). Story 4.4 should follow: implement → run review → apply review patches in a follow-up commit.
- **Tests follow source file structure** — `services/foo.py` → `tests/test_services/test_foo.py`, `views/foo.py` → `tests/test_api/test_foo.py` (or `test_views/` if it existed; today everything view-level lives in `test_api/` despite the name). The new optout view tests live in `test_api/test_optout.py` per this convention. **Do NOT** create a `test_views/` directory for one file.
- **Public test files use Django's `Client`, JSON test files use DRF's `APIClient`.** Mixing them is a source of confusion — `Client.post(url)` posts as form-encoded by default, while `APIClient.post(url)` posts as JSON. The optout view expects form-POSTs (the visible button on the confirm page), so the `Client` is correct.
- **Migration numbering is strict** — every PR adds at most one migration. This story adds **zero migrations** (no model changes).

### Latest Tech Information

- **Django 6.0.3 (`django==6.0.3` per pyproject.toml line 11):**
  - `signing.TimestampSigner.sign_object` and `unsign_object` are stable APIs in Django 4+ and unchanged in 6.x. No deprecation warnings expected. The `salt` parameter is the standard scope-isolation mechanism — used identically by `PasswordResetTokenGenerator`.
  - `BadSignature` and `SignatureExpired` are the two exception types from `django.core.signing`. `SignatureExpired` is a subclass of `BadSignature` — catching `BadSignature` covers both.
  - `csrf_exempt` and `require_http_methods` are stdlib; no API changes.
  - HTML response: `HttpResponse(body, content_type="text/html")` — `content_type` is the kwarg, NOT `mimetype` (the latter was deprecated long ago).
- **Django test client:**
  - `Client()` returns `Response` with `.content` (bytes) and `.status_code` (int). Use `b"..." in response.content` for substring assertions.
  - `Client.post(url)` defaults to `application/x-www-form-urlencoded`. For the optout view, an empty POST body is sufficient (the form has no fields beyond the submit button).
  - `Client.get(url, follow=False)` — default. Don't follow redirects (the optout view does not redirect; it returns 200 directly).
- **`pytest-django==4.12.0`:** the `@pytest.mark.django_db` and `client` / `db` fixtures are unchanged. No new patterns required.
- **`signing.TimestampSigner` token format:** `<base64-payload>:<base64-timestamp>:<base64-hmac>`. URL-safe characters only — no escaping required when interpolating into a URL path. Token length for a `(email, account_id)` payload is ~80-120 chars depending on email length. Fits well within email-client URL length limits (~2048 chars typical).

### References

- [Source: _bmad-output/epics.md — Epic 4, Story 4.4 lines 868-892, FR26-27 lines 44-45 / 163-165]
- [Source: _bmad-output/prd.md — FR26 (line 503), FR27 (line 504), GDPR transactional classification (line 253), opt-out risk register (line 277), brand voice (line 115)]
- [Source: _bmad-output/architecture.md — Notification Service (line 34, line 821, line 898), public optout endpoint isolation (line 921-923), audit trail (line 94), tenant isolation (line 229-230), email provider (line 307), TenantScopedModel (line 444-447)]
- [Source: _bmad-output/ux-design-specification.md — Sophie's Journey 4 (line 733-771), opt-out check first in flow (line 739-740), opt-out respected = audit logged (line 797), opt-out non-prominent visible (line 769)]
- [Source: _bmad-output/4-1-resend-integration-branded-failure-notification-email.md — placeholder opt_out_url, gate sequence, NotificationOptOut model creation]
- [Source: _bmad-output/4-2-tone-selector-settings-live-notification-preview.md — notification_preview endpoint, escape patterns]
- [Source: _bmad-output/4-3-final-notice-recovery-confirmation-emails.md — `_render_email_shell` extraction (Task 2.3), generalized `_log_suppression(email_type=...)`, "both new builders MUST accept the URL as a parameter so 4.4 is a one-line caller-site change" (Dependencies section)]
- [Source: backend/core/models/notification.py — `NotificationOptOut` model (lines 55-67), `unique_opt_out_per_account` constraint, `NotificationLog` partial unique constraint (lines 40-52)]
- [Source: backend/core/tasks/notifications.py — `_passes_gates` Gate 4 (lines 64-69), `_log_suppression` (lines 376-416)]
- [Source: backend/core/services/email.py — `_render_email_shell` (lines 74-94), three placeholder opt_out_url assignments (lines 279, 337, 388)]
- [Source: backend/core/services/audit.py — `write_audit_event` (lines 11-50), actor enum docstring (line 25)]
- [Source: backend/core/views/account.py — `notification_preview` (lines 253-302), placeholder opt_out_url at line 283]
- [Source: backend/safenet_backend/urls.py — project URLConf (current state has 6 paths, 4.4 adds the public optout route)]
- [Source: backend/safenet_backend/settings/base.py — `SAFENET_SENDING_DOMAIN` (line 144), env pattern, settings layout]
- [Source: backend/core/models/base.py — `TenantScopedModel`, `TenantManager.for_account(account_id)` (lines 13-15), `Account` is NOT TenantScopedModel — it IS the tenant]
- [Source: backend/core/tests/test_models/test_notification.py — `NotificationOptOut` test fixtures (lines 187-211), `mid_account` fixture pattern (lines 25-32)]
- [Source: backend/core/tests/test_tasks/test_notifications.py — `mid_account`/`subscriber_with_email`/`failure` fixtures, `TestSendFailureNotification.test_opt_out_suppressed` pattern]
- [Source: Django docs — `django.core.signing.TimestampSigner.sign_object`, `unsign_object`, `BadSignature`, `salt` parameter for scope isolation]

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

- Full backend regression run (in-container): `docker compose run --rm web poetry run pytest -q` → 504 passed, 10 failed.
- The 10 failures are pre-existing on bare `main` (verified by stashing Story 4.4 changes and re-running the same suite — same 10 failures in `test_billing_webhook.py`, `test_dashboard.py`, `test_polling.py`). They are unrelated to Story 4.4 and are NOT regressions introduced by this story.
- Story 4.4-scoped tests: `test_optout_token.py` (9 tests), `test_optout.py` (20 tests), `test_optout_e2e.py` (1 e2e), updated `test_email.py`, and 3 new classes appended to `test_notifications.py` — all green.

### Completion Notes List

- **Token design (AC1):** Implemented `core/services/optout_token.py` exposing `build_optout_token`, `decode_optout_token`, `build_optout_url`. Uses `django.core.signing.TimestampSigner` with module-private salt `"safenet.notifications.optout"` and `sign_object({"email": <lowered>, "account_id": <int>})`. Stateless — no DB row, no expiry per FR26 / GDPR transactional contract; `unsign_object(..., max_age=None)` at decode time. Email canonicalization (`strip().lower()`) happens at both sign and gate-check time so the gate-4 `email__iexact` lookup matches what was signed.
- **Public view (AC2/AC3):** New `core/views/optout.py` — function view (NOT DRF) at `/optout/<token>/`, registered at the project URLConf level **outside** `/api/v1/` (architecture.md line 921-923). `@csrf_exempt @require_http_methods(["GET", "POST"])`. GET is read-only (defends against email-scanner / Gmail / Outlook link-prefetching auto-opt-outs); POST creates the row inside a `transaction.atomic()` savepoint and catches `IntegrityError` for idempotency (re-clicks across devices, replays, double-submits all collapse to a single row per the existing `unique_opt_out_per_account` constraint at notification.py:62-67). All three response paths use `_render_email_shell` for visual consistency with emails; `<meta name="robots" content="noindex,nofollow">` added to `<head>`.
- **Audit grammar extension (AC3):** Added `ACTOR_SUBSCRIBER = "subscriber"` to `core/models/audit.py` and updated the `write_audit_event` docstring in `core/services/audit.py`. No DB CHECK constraint exists on `actor` (model-level validation only), so the extension is a safe additive change. Audit row is written **only on the create path** — the `IntegrityError` branch skips the write so replays don't produce duplicate audit rows.
- **Email wiring (AC1):** `core/services/email.py` placeholder URL replaced at all 3 call sites (lines 279/337/388 — `send_notification_email`, `send_final_notice_email`, `send_recovery_confirmation_email`) with `build_optout_url(subscriber_email=..., account_id=account.id)`. `core/views/account.py` notification_preview also updated — uses `subscriber_email="preview@example.com"` so the live preview reads identically to a real email but the token never resolves to a real opt-out (FR26).
- **Suppression source-of-truth (AC4):** `_passes_gates` in `tasks/notifications.py:64-69` is unchanged. Story 4.4 only WIRES the user-facing surface; the existing Gate 4 already enforces suppression for all three email types. Verified end-to-end via `test_optout_e2e.py` (signing → email rendering → token extraction → public view → opt-out persistence → second-failure suppression by Gate 4) and via parametrized class `TestOptOutSuppressesAllEmailTypes`.
- **Tenant scoping (AC4):** `TestNotificationOptOutTenantScoping` confirms an opt-out from Brand A does NOT suppress notifications from Brand B for the same subscriber email — the existing `unique_opt_out_per_account` constraint and the gate's `account=account` filter give per-(email, account_id) scoping for free.
- **Settings:** Added `SAFENET_BASE_URL` to `safenet_backend/settings/base.py` (`env("SAFENET_BASE_URL", default="https://app.safenet.app")`) and to `.env.example` (`SAFENET_BASE_URL=http://localhost:8000`). Used by `build_optout_url` to produce fully-qualified URLs.
- **Observability:** Invalid-token branch logs only `type(exc).__name__` — never the raw token (token contains the subscriber email; logging the raw token would leak PII into logs).
- **Test infra note:** Tests must run inside docker (`docker compose run --rm web poetry run pytest`) — DATABASE_URL hostname `db` only resolves inside the docker network. Hit and recovered from this once during the run.

### File List

**Created (5):**
- `backend/core/services/optout_token.py`
- `backend/core/views/optout.py`
- `backend/core/tests/test_services/test_optout_token.py`
- `backend/core/tests/test_api/test_optout.py`
- `backend/core/tests/test_api/test_optout_e2e.py`

**Modified (9):**
- `backend/safenet_backend/urls.py` — registered `/optout/<token>/` at project URLConf
- `backend/safenet_backend/settings/base.py` — added `SAFENET_BASE_URL`
- `backend/.env.example` — added `SAFENET_BASE_URL=http://localhost:8000`
- `backend/core/services/email.py` — replaced 3× placeholder opt-out URL; added robots meta to `_render_email_shell`
- `backend/core/views/account.py` — notification_preview now uses `build_optout_url`
- `backend/core/services/audit.py` — extended `actor` docstring to include `"subscriber"`
- `backend/core/models/audit.py` — added `ACTOR_SUBSCRIBER` constant + `ACTOR_CHOICES` entry
- `backend/core/tests/test_services/test_email.py` — updated friendly-tone test to use `build_optout_url`
- `backend/core/tests/test_tasks/test_notifications.py` — appended 3 classes (`TestOptOutCanonicalEmailSuppression`, `TestNotificationOptOutTenantScoping`, `TestOptOutSuppressesAllEmailTypes`)

### Review Findings

_Adversarial code review run on 2026-04-27. Layers: Blind Hunter (24 findings), Edge Case Hunter (21 findings), Acceptance Auditor (5 findings). After dedup + triage: 10 patch, 11 defer, ~16 dismiss (explicit spec choices, false positives, informational)._

**Patches (unresolved — fix before sign-off):**

- [x] [Review][Patch] Decode error handling too narrow — `decode_optout_token` payload extraction in `optout_view` only catches `BadSignature`. Malformed (signature-valid, schema-mismatched) payloads raise `KeyError`/`TypeError`/`ValueError` and become 500s, leaking "valid signature, wrong shape" via status differential. Catch the broader family and validate types. [`backend/core/views/optout.py:73-84`]
- [x] [Review][Patch] `IntegrityError` catch is too broad — any DB integrity failure (FK, NOT NULL, future CHECK) is silently treated as "already opted-out" and returns the success page without persisting a row. Replace with `NotificationOptOut.objects.get_or_create(...)` so only the unique-violation path is treated as idempotent. [`backend/core/views/optout.py:107-114`]
- [x] [Review][Patch] Audit + subscriber lookup outside the savepoint — if `write_audit_event` or `Subscriber.for_account(...).filter(...).first()` raises (DB hiccup, immutable-save misfire), the opt-out row is committed but no audit row exists. Wrap the create + lookup + audit in a single `transaction.atomic()`. [`backend/core/views/optout.py:108-137`]
- [x] [Review][Patch] No `Cache-Control: no-store` header on responses — confirm/success/invalid pages return 200 with no caching directive. Corporate proxies / CDNs may cache the per-token URL with company-name HTML. Add `response["Cache-Control"] = "no-store, private"` on all three render paths. [`backend/core/views/optout.py:81,96,144`]
- [x] [Review][Patch] `_render_invalid_page` produces a visible empty `<h2></h2>` block — the shared `_render_email_shell` always emits the brand `<h2>`, leaving ~36px of blank header space when called with `escaped_company=""`. Suppress the `<h2>` when `escaped_company` is empty (or pass a neutral string). [`backend/core/views/optout.py:65` / `backend/core/services/email.py:90`]
- [x] [Review][Patch] Form action uses `request.path` instead of `reverse()` — works today but is fragile to URLConf changes / proxy path injection. Replace with `reverse("notification_optout", kwargs={"token": token})`. [`backend/core/views/optout.py:97`]
- [x] [Review][Patch] e2e test extracts token via fragile regex without verifying payload — `re.search(r"/optout/([^/\"]+)/")` silently misses if HTML escapes `/`, and the test never decodes the extracted token to verify it carries the right `(email, account_id)`. Use `build_optout_url(...)` to assert the URL appears verbatim, then decode the extracted token and assert payload matches `{"email": "sub@x.com", "account_id": mid_account.id}`. [`backend/core/tests/test_api/test_optout_e2e.py:82-88`]
- [x] [Review][Patch] `test_email_lookup_case_insensitive` is misnamed and under-tested — it only verifies the signer's `strip().lower()` canonicalization, not that a token signed with one casing suppresses notifications for a `Subscriber.email` stored with different casing. Rename to `test_post_canonicalizes_email_at_sign_time` and add a separate test that signs with mixed case + verifies Gate 4 suppression of the lower-case stored email. [`backend/core/tests/test_api/test_optout.py:123-128`]
- [x] [Review][Patch] `caplog` test asserts on `r.message` (format string) not `r.getMessage()` (formatted output) — false-negative if a future patch adds the raw token to log args. Switch the negative assertion to check `r.getMessage()` and `str(r.args)` so a real leak is caught. [`backend/core/tests/test_api/test_optout.py:228-235`]
- [x] [Review][Patch] `test_invalid_token_does_not_leak_account_existence` does not assert byte-identical responses — both the bad-signature and account-not-found branches return the same `_render_invalid_page`, but the test only asserts `status==200` and `"no longer valid" in body`. Add an assertion that the response bytes match a tampered-token response exactly (no per-branch differential). [`backend/core/tests/test_api/test_optout.py:141-146`]

**Deferred (acknowledged, not in scope for this story):**

- [x] [Review][Defer] No token rotation / revocation primitive — explicit design decision per FR26 / GDPR transactional contract (`max_age=None`, no per-subscriber DB nonce). Documented in spec.
- [x] [Review][Defer] `@csrf_exempt` POST without nonce — explicit design decision per spec ("Do NOT add CSRF protection… signed token IS the proof-of-intent"). Re-evaluate if `RFC 8058 List-Unsubscribe-Post` header support is added.
- [x] [Review][Defer] `account_id` enumeration if `SECRET_KEY` leaks — accepted via stateless-token design (no per-subscriber secret). If `SECRET_KEY` is rotated, all old opt-out URLs break.
- [x] [Review][Defer] Unicode NFKC canonicalization for non-ASCII emails — `str.lower()` is locale-naive (Turkish dotless İ, German ß). Project-wide concern; gate-4 lookup at `notifications.py:64` has the same gap. Address in a follow-up touching all email-canonicalization sites.
- [x] [Review][Defer] DB unique constraint on `NotificationOptOut(subscriber_email, account)` is case-sensitive but gate-4 lookup is `__iexact` — mixed-case rows inserted via operator console / future API could bypass the duplicate guard. Story 4.1 model-layer concern; not in scope here.
- [x] [Review][Defer] `SAFENET_BASE_URL` scheme validation — no fail-loud check that the env var is `https://` (or `http://localhost`). Settings-layer hardening; defer.
- [x] [Review][Defer] No max email length enforcement at sign time — only matters with `SECRET_KEY` leak. Cosmetic; defer.
- [x] [Review][Defer] Audit metadata stores raw `subscriber_email` PII — project-wide audit-logging policy (Sentry/SIEM redaction); not unique to this story.
- [x] [Review][Defer] `Subscriber.first()` non-deterministic if multiple subscribers share an email under one account — project-wide subscriber-model concern; not in scope.
- [x] [Review][Defer] `_render_email_shell` is a private (`_`-prefixed) import across modules — explicitly deferred per spec Task 2.6. Promote to public if a third public-HTML page is added (Story 4.5 password reset is the trigger).
- [x] [Review][Defer] `int(account_id)` raises uncaught for non-numeric input — defensive only; today every caller passes `account.id` (`BigAutoField`). No current risk.

## Change Log

| Date       | Version | Description                                                                                  | Author |
|------------|---------|----------------------------------------------------------------------------------------------|--------|
| 2026-04-27 | 1.0     | Story 4.4 implementation: stateless TimestampSigner opt-out token, public `/optout/<token>/` GET-then-POST view, all 3 email types wired, `subscriber` actor added to audit grammar, FR26 suppression validated end-to-end. | Dev (claude-opus-4-7) |
| 2026-04-27 | 1.1     | Adversarial code review (3 layers): 10 patch, 11 defer, ~16 dismissed. Findings appended.    | Reviewer (claude-opus-4-7) |
| 2026-04-27 | 1.2     | All 10 review patches batch-applied to view + tests + email shell.                           | Reviewer (claude-opus-4-7) |
