# Acceptance Auditor Findings

- **Throttle 429 message string does not match the API Contract** `[CRITICAL]`
  - **Violates:** AC 5; API Contracts table (`/api/v1/auth/password-reset/` 429 row and `/api/v1/auth/password-reset/confirm/` 429 row).
  - **Evidence:** Spec contract requires `error.message == "Too many password reset requests. Try again later."` for 429s. The implementation only adds a `Throttled → "RATE_LIMITED"` code mapping in `backend/core/views/errors.py`; the message is computed by `_get_error_message(response.data)` from DRF's default `Throttled.detail`, which is `"Request was throttled. Expected available in N seconds."`. No override is performed. Tests `test_throttle_5_per_min_on_confirm` only assert `error.code == "RATE_LIMITED"`, so the contract drift is not caught by tests either.

- **Frontend generic confirmation message does not match the spec verbatim and ignores the API response** `[MAJOR]`
  - **Violates:** AC 1 ("the frontend renders the same generic confirmation message verbatim"); Task 9.4 (which prescribes `setMessage(res.data?.data?.message ?? GENERIC)`).
  - **Evidence:** `frontend/src/app/(auth)/forgot-password/page.tsx:10-11` defines `GENERIC_CONFIRMATION = "If an account exists for that email, we've sent a reset link. Check your inbox."` — appends `" Check your inbox."` not present in the backend's spec'd body `"If an account exists for that email, we've sent a reset link."`. The component never reads `res.data?.data?.message`; it discards the API response and renders the local constant unconditionally.

- **Password-reset email body is missing the greeting paragraph** `[MAJOR]`
  - **Violates:** AC 6 ("the inner HTML contains: a greeting paragraph, one explanatory paragraph (...), a CTA button (...), and a single safety footer paragraph").
  - **Evidence:** `backend/core/services/email.py` `_build_password_reset_html_body` renders only the explanatory paragraph + CTA + footer. No greeting (`Hi`/`Hello`) paragraph is present. Spec lists four blocks; impl produces three.

- **Story 4.4 scope creep bundled into the 4.5 diff** `[MAJOR]`
  - **Violates:** "File List in Dev Agent Record" / scope discipline.
  - **Evidence:** The diff modifies files outside the spec File List and outside Story 4.5 concerns:
    - `backend/core/models/audit.py` (adds `ACTOR_SUBSCRIBER` enum + choice — Story 4.4)
    - `backend/core/services/audit.py` (adds `"subscriber"` to docstring — explicitly stated in spec Task 11.1 as "No update needed")
    - `backend/core/views/account.py` (replaces opt-out URL placeholder with `build_optout_url` — Story 4.4)
    - `backend/core/services/email.py` non-4.5 portions: introduces `build_optout_url` import, replaces three `"https://app.safenet.app/notifications/opt-out"` placeholders, adds `<meta name="robots" content="noindex,nofollow">` to `_render_email_shell`, adds the empty-company-header branch — all Story 4.4 carry-over.
    - `backend/core/tests/test_tasks/test_notifications.py`, `backend/core/tests/test_services/test_email.py` updated for the above.
  - Spec Task 11.1 explicitly states: "**No update needed** to `core/services/audit.py` docstring — the actor enum already includes `'client'`". The diff updates that docstring anyway.

- **`backend/core/views/errors.py` is modified but not declared in the spec File List** `[MINOR]`
  - **Violates:** File List in Dev Notes (Project Structure Notes, lines 1001-1010).
  - **Evidence:** The original spec File List does not include `backend/core/views/errors.py`. The completion notes do mention it, but the spec's authoritative File List omits it. The change itself is required for AC 5.

- **Confirm endpoint logging collapses `user_not_found` into `bad_uid` reason code** `[MINOR]`
  - **Violates:** AC 7 (structured log enum: `reason=<bad_uid|user_not_found|check_token_failed|password_invalid>`).
  - **Evidence:** `backend/core/views/password_reset.py` catches `(TypeError, ValueError, OverflowError, User.DoesNotExist)` together and emits `reason=bad_uid` regardless. The `user_not_found` differential exists in the spec's enum (operator-side telemetry) but the implementation does not emit it.

- **No `time.sleep(0)` no-op on the unregistered-email branch** `[MINOR]`
  - **Violates:** AC 7 ("the fast-path 'user not found' still does a single dummy `time.sleep(0)` no-op").
  - **Evidence:** `backend/core/views/password_reset.py` returns immediately on the unknown-email branch with no dummy delay. Spec acknowledges this is best-effort but still requires the no-op call as a placeholder.

- **`DeadLetterLog` write is silently skipped for users without an Account** `[MINOR]`
  - **Violates:** AC 6 + Audit Trail block (the dead-letter row is the system-of-record for the failure).
  - **Evidence:** `backend/core/views/password_reset.py` wraps DLL creation in `if account is not None: DeadLetterLog.objects.create(...)`. If `user.account` is missing, the failure is logged via the bare logger only; no DLL row exists and the failure becomes invisible to the dead-letter operator dashboard.

- **Spec Task 5.1 pseudocode field `task=` does not match the actual `DeadLetterLog` schema** `[MINOR — spec error, not impl error]`
  - **Violates:** Spec internal consistency between Task 5.1 (`task="password_reset_email"`) and the actual `DeadLetterLog` field `task_name`.
  - **Evidence:** Implementation correctly uses `task_name="password_reset_email"`. The spec's pseudocode says `task=...` which would raise `TypeError`. This is a spec defect.

- **`reason=user_not_found` test coverage absent** `[MINOR]`
  - **Violates:** AC 7.
  - **Evidence:** `test_unknown_user_returns_400` validates the 400 response but does not assert any log-line `reason=` value. There is no test that distinguishes `bad_uid` from `user_not_found`.

- **Frontend `useSearchParams` Suspense refactor undocumented in spec** `[MINOR]`
  - **Violates:** Task 9.3 (does not mention Suspense boundary).
  - **Evidence:** `frontend/src/app/(auth)/login/page.tsx` wraps the inner component in `<Suspense fallback={null}>`. Completion Notes do call this out; spec Task 9.3 did not anticipate it. Implementation choice is correct.

- **Confirm-endpoint test `test_throttle_5_per_min_on_confirm` only validates `code`, not message** `[MINOR]`
  - **Violates:** API Contract testing rigor.
  - **Evidence:** Test asserts `r.status_code == 429` and `error.code == "RATE_LIMITED"` but never asserts the message string.

- **Request throttle 429 has no test for `code` or `message`** `[MINOR]`
  - **Violates:** AC 5 testing rigor.
  - **Evidence:** `test_throttle_blocks_after_3_requests_per_email` asserts only `r.status_code == 429`. The error envelope shape is never asserted on the request endpoint.

- **`test_password_reset_timeout_setting_is_one_hour` is a structural-only assertion** `[MINOR]`
  - **Violates:** AC 2 — would benefit from a behavioral test.
  - **Evidence:** Test only checks `settings.PASSWORD_RESET_TIMEOUT == 3600`. Spec permits this fallback when `freezegun` isn't installed, so sanctioned but timing behavior remains untested.
