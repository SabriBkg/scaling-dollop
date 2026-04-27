- **Open redirect / SSRF in `SAFENET_FRONTEND_URL`**
  `password_reset.py` constructs `reset_url = f"{base}/reset-password/{uidb64}/{token}"` from `settings.SAFENET_FRONTEND_URL` with no validation. If an operator misconfigures this env var (or it gets injected via a misconfigured deploy), the email goes out with attacker-controlled link and credentials are funneled offsite. There's no allowlist, no scheme check, and no warning if it stays at the dev `http://localhost:3000` default in production.

- **Anonymous unauthenticated bulk DLL writes / DoS amplification**
  In `password_reset_request`, on Resend failure the view writes to `DeadLetterLog` per-request for any registered email. An attacker who knows a single registered email can spam the request endpoint after the per-email throttle resets across IPs/hours and balloon the DLL table. Worse, a Resend outage will create one DLL row per legitimate user retry — unbounded growth, no dedupe.

- **Token expiry test is a tautology, not a guard**
  `test_password_reset_timeout_setting_is_one_hour` asserts `dj_settings.PASSWORD_RESET_TIMEOUT == 3600`. This proves the setting equals what the test says it should; it does not prove a token actually expires. A real test with `freezegun` (or Django's `signing` time-travel) is needed. The comment dismisses this as "freezegun not installed" — that's a missing dependency, not a justification.

- **Throttle key collision / forgery via attacker-chosen email**
  `PasswordResetRequestThrottle.get_cache_key` keys on `request.data["email"]` (post-strip+lower) and only falls back to IP when blank. An attacker can rotate `email` per request (e.g. `a+1@x.com`, `a+2@x.com`) to keep each request in its own bucket and bypass the 3/hour limit entirely. The per-email scheme without a coupled per-IP scheme is trivially defeated.

- **Audit metadata still risks PII reversal**
  `_email_hash` truncates SHA-256 to 16 hex chars (64 bits) with no salt. For any known target email list, that hash is precomputable; the audit log effectively stores a recoverable email identifier. Use a keyed HMAC with a server secret if the goal is opacity.

- **`get_ident` IP fallback trusts client headers**
  `PasswordResetConfirmThrottle` and the email fallback both call `self.get_ident(request)`. DRF's `get_ident` uses `X-Forwarded-For` when `NUM_PROXIES` is set; if proxies are misconfigured (or absent), an attacker setting `X-Forwarded-For: <random>` per request bypasses both the per-IP confirm throttle and the empty-email fallback.

- **Username/email confusion in `User.objects.filter(email__iexact=...)`**
  Django's stock `User` model does not enforce uniqueness on `email`. If two users share an email (legit duplicate from a prior bug, or a deliberate registration race), `.first()` silently picks one — sending a reset link that, when used, changes a *different* user's password than the one expected, or never reaches the actual account holder. There's no "no duplicates" guard.

- **`force_str(urlsafe_base64_decode(uid_raw))` accepts attacker-controlled bytes as a PK**
  Decoded value is passed to `User.objects.get(pk=user_pk)` without validating it's a positive integer. On PostgreSQL with integer PKs the queryset will raise `ValueError`, which is caught — fine. But on databases or model overrides where pk is a string/UUID, malformed input could leak through to the ORM with surprising matches. Also: `pk=user_pk` is a string compare in some backends, raising `DataError` not `ValueError`, which is *not* in the except tuple → 500.

- **`new_password`/`new_password_confirm` field has no max length**
  `serializers.CharField(write_only=True)` with no `max_length` means an attacker can submit a 10MB password. Django's Argon2 hasher will dutifully chew through it — a cheap DoS through repeated 6/min attempts before throttling. Compare with a `max_length=128`.

- **Invalid-link branch order leaks user existence via timing**
  `password_reset_confirm` returns immediately on `User.DoesNotExist` (cheap path), but on a real user does `check_token` (HMAC compute) and then runs the password validators (Argon2-similarity hash compute). The two branches that produce `INVALID_RESET_LINK` have wildly different latency profiles, so an attacker brute-forcing UIDs can distinguish "no such user" from "valid user, bad token" via timing despite the byte-identical body.

- **Cache headers missing on the request endpoint and on error responses**
  The success body of `password_reset_confirm` sets `Cache-Control: no-store, private`, but `password_reset_request` (and all 400 responses from confirm) do not. A reverse-proxy that caches POST-with-body (some do under aggressive configs) could surface the generic 200 to other clients, or worse, surface a `INVALID_RESET_LINK` error response inappropriately.

- **Frontend silently swallows non-validation errors on `/forgot-password`**
  The catch block in `forgot-password/page.tsx` discards every error and renders the generic confirmation. Network failures, 500s, and CORS issues all show "we sent the link" — users will wait for an email that never comes, and there's no telemetry hook to flag systemic outages.

- **Token in URL path is preserved in browser history & referer**
  The reset URL `/reset-password/{uid}/{token}` is in the URL bar. After `router.replace(...)`, the previous URL stays in browser history; any third-party script loaded on that page (or HTTP `Referer` to non-same-origin assets) can exfiltrate the token. Also the SafeNet email content and any preview tools that prefetch the URL (Outlook Safe Links, Slack unfurl, corporate mail scanners) will *consume* the single-use token before the user clicks.

- **Login `?reset=success` query param is not sanitized in the success banner**
  `searchParams.get("reset") === "success"` is exact-match, so XSS is fine here, but the `role="status"` banner is rendered unconditionally without rate-limiting; an attacker can craft `?reset=success` links and seed phishing pages that look like a successful reset.

- **`hashlib.sha256(email.encode())` — implicit UTF-8, no normalization**
  Email `Müller@x.com` and the NFD-decomposed form hash differently. Throttle bucket and audit hash will diverge for the "same" email in different inputs. A determined attacker can use Unicode-equivalent email forms to get N×3 attempts.

- **`api_view`-based endpoints don't disable browsable API renderer**
  The two new endpoints inherit DRF defaults; if `BrowsableAPIRenderer` is enabled globally, GET to these URLs returns an HTML form. POST is the only action defined, but the metadata page still leaks the endpoint shape (and, depending on config, the throttle scope/rate). Consider explicit `renderer_classes([JSONRenderer])`.

- **`from core.models.dead_letter import DeadLetterLog` inside the except**
  Lazy import inside a try/except in the request hot path. If the module fails to import (circular, packaging issue), the catch-all `except Exception` swallows it and still returns 200 — the DLL is silently never written. Move the import to module top, surface ImportError early.

- **`account = user.account if hasattr(user, "account") else None`**
  Mixing `hasattr` with a related-object accessor on a Django model is the classic anti-pattern: `hasattr` masks any exception (including `RelatedObjectDoesNotExist`, `DatabaseError`) and proceeds with `account=None`. Use `getattr(user, "account", None)` or a try/except on the specific exception. Same anti-pattern repeated three times in the file.

- **Audit `actor="client"` for an anonymous reset is misleading**
  The audit row's `actor` is "client" with no IP, no UA, no request fingerprint. For a security-relevant event ("password reset requested/completed") a SOC needs source IP and UA at minimum to investigate account-takeover patterns. The audit metadata records only `user_id` and `email_hash` — useless for forensics.

- **Test does not assert `Content-Length` byte-equality**
  The spec requires byte-identical responses but the test deliberately does not assert that `Content-Length`, response headers, and timing are also identical. The "no enumeration" promise is broken if the registered-email path takes 200ms (Resend round-trip) and the unknown path takes 5ms.

- **Frontend `params.uid` / `params.token` typed but not validated**
  `useParams<{ uid: string; token: string }>()` returns whatever's in the URL — could be empty strings, could be `undefined` if the route shape ever changes. The handler posts them straight to the API.

- **No CSRF protection / Origin check on the confirm endpoint**
  The confirm endpoint accepts JSON POST from any origin. If a victim is tricked into submitting a form to `/api/v1/auth/password-reset/confirm/` with attacker-supplied uid/token/new_password, the password is set without further confirmation. No Origin/Referer check.

- **`subject = "Reset your SafeNet password"` is non-localized**
  Hardcoded English string in `_build_password_reset_subject`.

- **`opt_out_url = build_optout_url(...)` called even when subscriber.email is empty** (cross-cutting)
  In `send_notification_email`, `(subscriber.email or "").strip().lower()` may be `""`, and that empty string is passed to `build_optout_url`. (This may be a pre-existing concern; flagged from the diff hunks visible.)

- **`force_str(urlsafe_base64_decode(uid_raw))` does not reject leading-zero / numeric collisions**
  Compare with `int(force_str(...))` plus explicit positive check.

- **Tests assert `mock_resend.call_args[0][0]` — positional, fragile**
  If `resend.Emails.send` ever moves to kwargs, every call_args[0][0] assertion silently breaks. Use `call_args.kwargs` or `call_args.args` explicitly with a fallback.

- **`test_throttle_falls_back_to_ip_for_blank_email` does not assert the bucket prefix is `_anon_<ip>`**
  If a future refactor merges the buckets, the test still passes while real behavior diverges.

- **`/api/v1/auth/password-reset/` and `APPEND_SLASH=True`**
  POST without trailing slash causes Django to issue a 301 redirect that, with some clients, drops the body — the user gets a generic 200 of nothing or an error. APPEND_SLASH-on-POST is a known foot-gun.

- **No unit test for `_build_password_reset_html_body` rendering empty `reset_url`**
  If `reset_url` is somehow `""`, the email goes out with `<a href="">Reset password</a>` — clicking opens the user's own inbox.

- **`logger.error(...)` drops the actual exception object**
  No `exc_info=True`, no stack. Compare with `logger.exception(...)` so operators see the trace.

- **Suspense fallback is `null`**
  The login page wraps in `<Suspense fallback={null}>`. During hydration the entire page is invisible — a CLS regression and degraded UX during slow loads.
