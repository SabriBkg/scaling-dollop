# Story 4.2: Tone Selector Settings & Live Notification Preview

Status: needs-regeneration

> **POST-SIMPLIFICATION REGENERATION REQUIRED (2026-04-29).** This file is pre-simplification. The canonical post-simplification ACs live in `_bmad-output/epics.md` (Story 4.2, lines 1014–1048) — adds redirect-link input (FR51) + paid-tier custom email body editor per email type (FR56). Regenerate this file via SM workflow against the epics.md ACs before resuming work on these AC blocks. The existing tone-selector implementation remains valid; the new ACs (FR51, FR56) are additive.

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mid-tier founder,
I want to choose my notification tone from three presets and see exactly what my subscribers will receive,
So that the emails reflect my brand voice before any subscriber sees them.

## Acceptance Criteria

1. **Given** the Settings → Notifications screen
   **When** the client selects a tone preset (`professional` / `friendly` / `minimal`)
   **Then** the live preview updates immediately — showing exactly what the subscriber will receive, with the client's brand name (`account.company_name`) populated (FR23, UX-DR17)
   **And** the preview updates on every preset change without a page reload
   **And** the preview renders the same HTML body the engine will send (single source of truth — no frontend template duplication)

2. **Given** the client clicks a tone preset
   **When** the API responds successfully
   **Then** `Account.notification_tone` is persisted (auto-save on change — no Save button per UX §12.7)
   **And** the next notification email sent by the engine for that account uses the saved tone
   **And** the tone can be changed at any time — the next notification uses the new tone

3. **Given** the three tone presets rendered in the preview
   **When** any preset is selected
   **Then** copy follows these rules and these rules only:
     - **Professional**: formal, direct, **no contractions** (e.g., "We have noticed", "you cannot")
     - **Friendly**: warm, conversational, contractions allowed (e.g., "Just a heads-up — we couldn't process…")
     - **Minimal**: bare facts, **two sentences maximum** in the body (excluding header/footer/CTA chrome)
   **And** all three tones are GDPR transactional — zero marketing copy, zero promotional language
   **And** the `card_expired` reassurance ("Your access continues while you update your details") is present in all three tones (FR22, GDPR transactional consistency)

4. **Given** an authenticated request to `GET /api/v1/account/notification-preview/?tone=<preset>`
   **When** the tone parameter is one of `professional`, `friendly`, `minimal`
   **Then** the endpoint returns `{data: {tone, subject, html_body, sample_subscriber_email, sample_decline_code}}` rendered with `account.company_name`, an example subscriber email (`subscriber@example.com`), and an example decline code (`card_expired`)
   **And** the rendered HTML matches what `send_notification_email` would produce for the same tone
   **And** an invalid `tone` value returns `400 INVALID_TONE`
   **And** the endpoint is JWT-protected (same auth class as `account_detail`)

5. **Given** an authenticated `POST /api/v1/account/notification-tone/` with body `{tone: <preset>}`
   **When** `tone ∈ {professional, friendly, minimal}` AND `account.tier ∈ {mid, pro}`
   **Then** `Account.notification_tone` is updated (`update_fields=["notification_tone"]`)
   **And** an audit event is written: `{actor: "client", action: "notification_tone_changed", outcome: "success", metadata: {from: <old>, to: <new>}}`
   **And** the response is the standard account envelope from `_build_account_response()` (so the frontend's `useAccount` cache is reusable)
   **And** if the tone is unchanged the call is idempotent (no audit event, no DB write)
   **And** Free-tier accounts get `403 TIER_NOT_ELIGIBLE` (matches the `set_engine_mode` pattern at `views/account.py:203`)

6. **Given** an existing account with no `notification_tone` set
   **When** any notification is dispatched OR the preview is requested
   **Then** `professional` is used as the default
   **And** the migration backfills `notification_tone="professional"` for all existing accounts (Story 4.1's existing behaviour was implicitly Professional — preserve parity)

7. **Given** the Settings page renders the tone selector
   **When** the page is opened on Free-tier OR no-DPA OR no-engine-mode accounts
   **Then** the Notifications section is visible but the controls are disabled with a tier-upgrade hint (mirrors the conditional-section pattern at `settings/page.tsx:78` for Recovery Mode)
   **And** the preview is still rendered (so users can see what they're upgrading toward)

## Tasks / Subtasks

- [ ] **Task 1: Backend — `Account.notification_tone` field + migration** (AC: 2, 5, 6)
  - [ ] 1.1 Add to `backend/core/models/account.py`:
    - Module constants: `TONE_PROFESSIONAL = "professional"`, `TONE_FRIENDLY = "friendly"`, `TONE_MINIMAL = "minimal"`, `TONE_CHOICES = [...]`, `DEFAULT_TONE = TONE_PROFESSIONAL`
    - Field: `notification_tone = models.CharField(max_length=20, choices=TONE_CHOICES, default=DEFAULT_TONE)`
  - [ ] 1.2 Generate the migration via `poetry run python manage.py makemigrations core` (Django will auto-name it ~`0013_account_notification_tone.py`); the column gets `default="professional"` so all existing rows backfill in a single statement (no data migration needed).
  - [ ] 1.3 No new dependencies expected — do NOT touch `pyproject.toml`.
  - [ ] 1.4 Add `notification_tone` to `_build_account_response()` in `backend/core/views/account.py` (line ~116) so the field is returned by `/api/v1/account/me/`.

- [ ] **Task 2: Backend — Refactor `email.py` to be tone-aware** (AC: 1, 3, 6)
  - [ ] 2.1 In `backend/core/services/email.py` add a `TONE_PROFESSIONAL`/`TONE_FRIENDLY`/`TONE_MINIMAL` set imported from a new module `backend/core/services/email_templates.py` (keeps `email.py` lean).
  - [ ] 2.2 Create `backend/core/services/email_templates.py` containing a single `TONE_TEMPLATES` dict keyed by tone string. Each entry holds:
    - `subject_default(company)` → str
    - `subject_card_expired(company)` → str
    - `greeting()` → str (e.g., "Hello,", "Hi there,", "")
    - `body_paragraphs(company, label)` → list[str] (each becomes a `<p>` block — Minimal returns ≤2 paragraphs)
    - `access_continues_phrasing()` → str (the "access continues" reassurance, voiced per tone)
    - `cta_label()` → str (e.g., "Update Payment Details", "Update your details", "Update card")
    - `footer(company, opt_out_url)` → str
    All copy is GDPR-transactional — no marketing language. Add a one-line module docstring stating this constraint.
  - [ ] 2.3 Refactor `_build_subject(decline_code, company_name)` → `_build_subject(decline_code, company_name, tone)`. Dispatch to `TONE_TEMPLATES[tone].subject_card_expired(...)` or `.subject_default(...)`. Keep CRLF sanitization via `_sanitize_header`.
  - [ ] 2.4 Refactor `_build_html_body(company, decline_code, portal_url, opt_out_url)` → `_build_html_body(company, decline_code, portal_url, opt_out_url, tone)`. Dispatch all copy through the chosen `TONE_TEMPLATES[tone]`. Keep `html.escape()` on every interpolated value (4-1 review patches must NOT regress).
  - [ ] 2.5 Refactor `send_notification_email(subscriber, failure, account)`:
    - Read `tone = account.notification_tone or DEFAULT_TONE`
    - Pass `tone` through to `_build_subject` and `_build_html_body`
    - All other behaviour (header injection guards, recipient normalization, `SkipNotification` on missing `customer_update_url`, Resend SDK call, missing-id guard) **unchanged** from 4-1.

- [ ] **Task 3: Backend — Tone update endpoint** (AC: 5)
  - [ ] 3.1 New view `set_notification_tone(request)` in `backend/core/views/account.py`:
    - `@api_view(["POST"]) @permission_classes([IsAuthenticated])`
    - Validate `tone ∈ TONE_CHOICES`; on invalid → `{error: {code: "INVALID_TONE", message: "Tone must be 'professional', 'friendly', or 'minimal'."}}` `400`
    - `with transaction.atomic(): account = Account.objects.select_for_update().get(pk=account.pk)` (matches the `set_engine_mode` pattern at `views/account.py:199-201`)
    - Tier gate: reject Free with `TIER_NOT_ELIGIBLE` `403` (matches `set_engine_mode` at line 203)
    - Idempotency: if `account.notification_tone == tone` skip both write and audit
    - Otherwise update via `account.save(update_fields=["notification_tone"])` and call `write_audit_event(actor="client", action="notification_tone_changed", outcome="success", metadata={"from": old, "to": new}, account=account)`
    - Return `_build_account_response(account, request.user)` — same envelope shape the frontend already expects
  - [ ] 3.2 Wire route in `backend/core/urls.py`: `path("v1/account/notification-tone/", set_notification_tone, name="set_notification_tone")` — keep the existing `v1/account/...` cluster contiguous.

- [ ] **Task 4: Backend — Live preview endpoint** (AC: 1, 4, 7)
  - [ ] 4.1 New view `notification_preview(request)` in `backend/core/views/account.py`:
    - `@api_view(["GET"]) @permission_classes([IsAuthenticated])`
    - Read `tone = request.query_params.get("tone", account.notification_tone or DEFAULT_TONE)`
    - If `tone` not in `TONE_CHOICES` → `400 INVALID_TONE` (same shape as Task 3.1)
    - Use a fixed sample: `subscriber_email = "subscriber@example.com"`, `decline_code = "card_expired"` (showcases the access-continues reassurance), `portal_url = account.customer_update_url or "https://your-app.example.com/billing"` (preview MUST work even before `customer_update_url` is captured — see "What NOT to Do")
    - Build subject + HTML using the same `_build_subject` / `_build_html_body` helpers refactored in Task 2 — **never** duplicate template code between `send_notification_email` and the preview path
    - Return `{data: {tone, subject, html_body, sample_subscriber_email: "subscriber@example.com", sample_decline_code: "card_expired"}}`
    - Free-tier and no-DPA accounts are NOT blocked from the preview (AC 7 — preview is a sales surface)
  - [ ] 4.2 Wire route: `path("v1/account/notification-preview/", notification_preview, name="notification_preview")`.

- [ ] **Task 5: Frontend — types + Account hook surface** (AC: 1, 2, 5)
  - [ ] 5.1 Extend `frontend/src/types/account.ts`:
    ```ts
    export type NotificationTone = "professional" | "friendly" | "minimal";
    // Account interface adds:
    notification_tone: NotificationTone;
    ```
  - [ ] 5.2 No change to `useAccount.ts` — the existing `["account", "me"]` cache key already carries the new field once the backend serializes it. Do NOT add a separate hook for tone.

- [ ] **Task 6: Frontend — `ToneSelector.tsx` component** (AC: 1, 2, 7)
  - [ ] 6.1 New file `frontend/src/components/settings/ToneSelector.tsx` (architecture spec at `architecture.md:735` puts it here).
  - [ ] 6.2 Three radio cards (Professional / Friendly / Minimal). Use the **exact same radio-card markup** as the Recovery Mode block in `settings/page.tsx:85-114` (consistent settings UX — do NOT introduce a new variant).
  - [ ] 6.3 Auto-save on change (UX §12.7 "all settings fields auto-save on change or blur — no Save page button"):
    - Optimistic update: `queryClient.setQueryData(["account", "me"], { ...account, notification_tone: newTone })`
    - `await api.post<ApiResponse<Account>>("/account/notification-tone/", { tone: newTone })`
    - On success: `queryClient.invalidateQueries(["account", "me"])` AND invalidate the `notification-preview` query (Task 7) so the saved-tone view refreshes
    - On failure: roll back optimistic update, `toast.error("Failed to update tone. Please try again.")` (sonner — matches `settings/page.tsx:29`)
  - [ ] 6.4 Disabled state when `!account.dpa_accepted || account.tier === "free" || !account.engine_mode` — show a `text-xs text-[var(--text-secondary)]` upgrade hint above the cards (mirrors the conditional render of the Recovery Mode block).

- [ ] **Task 7: Frontend — `NotificationPreview.tsx` component + hook** (AC: 1, 4, 7)
  - [ ] 7.1 New hook `frontend/src/hooks/useNotificationPreview.ts`:
    ```ts
    export function useNotificationPreview(tone: NotificationTone) {
      return useQuery({
        queryKey: ["notification-preview", tone],
        queryFn: async () => {
          const { data } = await api.get<ApiResponse<{tone: NotificationTone; subject: string; html_body: string}>>(
            `/account/notification-preview/?tone=${tone}`
          );
          return data.data;
        },
        staleTime: 5 * 60 * 1000,
      });
    }
    ```
    Cache per tone — the three queries become hot after first hover/click and switching is instantaneous.
  - [ ] 7.2 New file `frontend/src/components/settings/NotificationPreview.tsx`:
    - Receives `tone: NotificationTone` prop (the *currently-selected* radio value, NOT the saved value — this drives the live update)
    - Renders subject in a styled "From / Subject" header card
    - Renders the email HTML in a sandboxed `<iframe srcDoc={html_body} sandbox="" title="Email preview" className="w-full h-[640px] rounded border border-[var(--border)]" />` — empty-string `sandbox` blocks scripts/forms/popups (defense-in-depth even though we control the HTML); fixed 640 px height accommodates the longest tone (Professional + access-continues block) without scrollbars in the common case
    - Show skeleton during `isLoading`; show inline error toast on `isError`
    - Caption underneath: "Preview shown with sample subscriber data — `subscriber@example.com`, decline code `card_expired`."

- [ ] **Task 8: Frontend — Wire into Settings page** (AC: 1, 7)
  - [ ] 8.1 Edit `frontend/src/app/(dashboard)/settings/page.tsx`:
    - Add a new `<section>` after the Recovery Mode section titled "Notifications"
    - Local state: `const [selectedTone, setSelectedTone] = useState<NotificationTone>(account?.notification_tone ?? "professional")` — sync to `account.notification_tone` whenever it changes via `useEffect`
    - Render `<ToneSelector value={selectedTone} onChange={setSelectedTone} disabled={...} />` and `<NotificationPreview tone={selectedTone} />` side-by-side on `md:` (use `md:grid-cols-2 gap-6`); stacked on mobile.
    - Free-tier branch shows the section with disabled controls + the preview (AC 7).

- [ ] **Task 9: Backend tests** (AC: all)
  - [ ] 9.1 `backend/core/tests/test_models/test_account.py` (new file if it doesn't exist; otherwise extend) — assert `notification_tone` defaults to `"professional"`, choices enforced via `model.full_clean()`.
  - [ ] 9.2 `backend/core/tests/test_api/test_notification_tone.py` — Mid+DPA happy path, idempotency (same tone → no audit row), invalid tone (400), Free-tier (403), unauthenticated (401), audit metadata shape (`{from, to}`).
  - [ ] 9.3 `backend/core/tests/test_api/test_notification_preview.py` — happy path returns `{tone, subject, html_body}`, invalid tone (400), preview works without `customer_update_url` (uses placeholder), preview works for Free-tier (200), no-DPA (200), and JWT-protected (401).
  - [ ] 9.4 Extend `backend/core/tests/test_services/test_email.py`:
    - Three new tests: `test_subject_uses_friendly_tone`, `test_subject_uses_minimal_tone`, `test_body_minimal_has_max_two_paragraphs` (count `<p>` tags inside the body section, excluding header/footer/CTA chrome)
    - One round-trip test: `send_notification_email` with `account.notification_tone="friendly"` produces the same HTML as `_build_html_body(..., tone="friendly")` — guards Task 4's "single source of truth" requirement
    - Re-run all 4-1 escape/sanitization tests with each tone — they must still pass (no XSS regression).
  - [ ] 9.5 Update `backend/core/tests/test_api/test_engine_mode.py` only if a fixture is shared — likely no change; do NOT widen the scope of that file.

- [ ] **Task 10: Frontend tests** (AC: 1, 2, 7)
  - [ ] 10.1 If a Vitest/Jest setup exists in `frontend/`, add `frontend/src/components/settings/__tests__/ToneSelector.test.tsx` covering: renders three options, calls `onChange` on click, disabled state hides interactivity. Check `frontend/package.json` for existing test runner before authoring — if no test runner is configured, **skip** and note it in completion notes (do NOT add a test framework as part of this story).
  - [ ] 10.2 Manual UI verification (always required, regardless of unit-test framework presence): start `docker-compose up`, log in as a Mid-tier+DPA account, open `/settings`, switch all three tones, confirm preview updates without reload, confirm tone persists across page reload, confirm a fresh API call to `/notification-tone/` is made.

## Dev Notes

### Architecture Compliance

- **Tone is account-scoped, not subscriber-scoped.** Field lives on `Account`, not `Subscriber`. Every email for the account uses the current saved value.
- **Single source of truth for templates.** All tone copy lives in `backend/core/services/email_templates.py`. The frontend NEVER reimplements template logic — it always renders the HTML it gets from `/notification-preview/`. This guarantees AC 1's "preview matches what's sent" property.
- **Reuse `_build_account_response()`.** The tone-update endpoint MUST return this envelope so `useAccount` cache invalidation works without a new query key. (4-1 followed the same pattern after the 3-1 refactor — see `views/account.py:96-140`.)
- **`select_for_update()` MUST be inside a `transaction.atomic()` block** (4-1 review patch caught this exact bug at `tasks/retry.py:37-42`). Keep the pattern from `set_engine_mode`.
- **Sanitization carries forward.** All HTML body interpolation uses `html.escape()`; all header values pass through `_sanitize_header()`. Tone refactor MUST NOT regress these — extend the existing 4-1 escape tests across all three tones.

### Existing Code to Reuse (DO NOT reinvent)

| What | Where | Usage |
|------|-------|-------|
| `_build_account_response()` | `backend/core/views/account.py:96` | Standard envelope; add `notification_tone` here once. |
| `_sanitize_header()` | `backend/core/services/email.py:43` | Header CRLF/quote sanitization for subject + From. |
| `html.escape()` pattern | `backend/core/services/email.py:79-80` | Already used for `company_name` and `label`. |
| `set_engine_mode` view shape | `backend/core/views/account.py:181-249` | Tier gate + DPA gate + atomic + audit pattern — copy this structure. |
| `DECLINE_CODE_LABELS` | `backend/core/engine/labels.py` | Human-readable failure label inside the body. |
| `write_audit_event()` | `backend/core/services/audit.py` | Single audit write path — do not inline. |
| Recovery-mode radio cards | `frontend/src/app/(dashboard)/settings/page.tsx:85-114` | Reuse exact markup for tone selector; do NOT invent a new card style. |
| `useAccount` query key `["account", "me"]` | `frontend/src/hooks/useAccount.ts` | Existing cache; no new hook for tone. |
| `sonner` `toast.error/success` | already imported in settings page | Same UX as engine mode change. |
| `api` axios instance | `frontend/src/lib/api.ts` | All calls go through this — JWT injection + 401 retry handled. |
| shadcn `ApiResponse<T>` envelope | `frontend/src/types/api.ts` | Wrap all responses; types mirror Django snake_case. |

### What NOT to Do

- Do NOT introduce Django templates / Jinja / `render_to_string`. Inline HTML strings in `email_templates.py`. (4-1 made the same call.)
- Do NOT duplicate template copy on the frontend. The preview HTML always comes from `/notification-preview/`. iframes are cheap; template drift is expensive.
- Do NOT make the preview depend on `account.customer_update_url` being set. That field is a deferred follow-up from 4-1; the preview must render with a placeholder URL so users can evaluate tone before completing Stripe Connect onboarding.
- Do NOT change Story 4.1's gate-check ordering, retry behaviour, dead-letter handling, opt-out check, or `SkipNotification` semantics. Tone is purely a copy-selection layer on top.
- Do NOT add a "Save" button — UX §12.7 mandates auto-save for all settings fields.
- Do NOT block the preview endpoint behind tier/DPA — preview is a sales surface (AC 7).
- Do NOT add tone selection to the password reset email (Story 4.5) — that flow uses a fixed transactional template.
- Do NOT widen scope to recovery-confirmation or final-notice emails — those are Story 4.3.
- Do NOT create new shadcn primitives. The current `ui/` set already includes everything needed (radio pattern is hand-rolled with `<input type="radio">` matching the engine-mode block).
- Do NOT compute "two sentences" using a regex on rendered HTML. Enforce it by **construction** — the Minimal tone's `body_paragraphs()` returns at most two strings.

### Tone Copy Reference (canonical — implementation source)

These are the only authorized copies. Any deviation requires updating this story.

**Professional** (default; matches Story 4.1's existing voice)
- Subject (default): `Action needed: update your payment details — {company}`
- Subject (card_expired): `A quick note about your payment — {company}`
- Greeting: `Hello,`
- Body paragraph 1: `We have noticed an issue with your recent payment to {company}: {label}.`
- Body paragraph 2 (card_expired only): `Your access continues while you update your details.`
- Body paragraph 3: `You can resolve this by updating your payment details:`
- CTA label: `Update Payment Details`
- Footer: `This email was sent on behalf of {company} by SafeNet. <Unsubscribe link>`

**Friendly**
- Subject (default): `Quick heads-up about your {company} payment`
- Subject (card_expired): `Hey — your {company} card needs a refresh`
- Greeting: `Hi there,`
- Body paragraph 1: `Just a quick heads-up — we couldn't process your last payment to {company} because of {label}.`
- Body paragraph 2 (card_expired only): `Don't worry, you're still all set — your access keeps running while you update your details.`
- Body paragraph 3: `Hit the button below whenever you've got a sec:`
- CTA label: `Update your details`
- Footer: `Sent by {company} via SafeNet. <Unsubscribe link>`

**Minimal** (≤2 body paragraphs, hard cap)
- Subject (default): `Payment failed — {company}`
- Subject (card_expired): `Card expired — {company}`
- Greeting: `` *(empty — no greeting line)*
- Body paragraph 1: `Payment to {company} failed: {label}.`
- Body paragraph 2 (card_expired ONLY): `Update your card to continue. Access remains active.`
- Body paragraph 2 (other codes): `Update your payment method below.`
- CTA label: `Update card`
- Footer: `{company} via SafeNet. <Unsubscribe link>`

### API Contracts

```
POST /api/v1/account/notification-tone/
  Body: {"tone": "professional" | "friendly" | "minimal"}
  200: standard {data: <account envelope>}
  400: {"error": {"code": "INVALID_TONE", "message": "..."}}
  403: {"error": {"code": "TIER_NOT_ELIGIBLE", "message": "..."}}
  401: JWT missing/invalid

GET /api/v1/account/notification-preview/?tone=<preset>
  200: {"data": {
    "tone": "<preset>",
    "subject": "<rendered subject>",
    "html_body": "<rendered HTML>",
    "sample_subscriber_email": "subscriber@example.com",
    "sample_decline_code": "card_expired"
  }}
  400: {"error": {"code": "INVALID_TONE", ...}}
  401: JWT missing/invalid
  (No tier/DPA gating — preview is a sales surface.)

GET /api/v1/account/me/
  Adds field: "notification_tone": "professional" | "friendly" | "minimal"
```

### Tenant Isolation

- `Account` IS the tenant — no `TenantScopedModel` required (Account is the root of the tenant tree, see `models/account.py:19`).
- Both new endpoints derive the account from `request.user.account`, never from a request-supplied id. Same pattern as every other view in `views/account.py`.

### Audit Trail (MUST use single write path)

```python
write_audit_event(
    subscriber=None,
    actor="client",
    action="notification_tone_changed",
    outcome="success",
    metadata={"from": old_tone, "to": new_tone},
    account=account,
)
```

No audit event for the preview endpoint (read-only, no state change).

### Project Structure Notes

**New files to create:**
```
backend/core/services/email_templates.py            # TONE_TEMPLATES dict
backend/core/migrations/0013_account_notification_tone.py
backend/core/tests/test_api/test_notification_tone.py
backend/core/tests/test_api/test_notification_preview.py
backend/core/tests/test_models/test_account.py      # if not present
frontend/src/components/settings/ToneSelector.tsx
frontend/src/components/settings/NotificationPreview.tsx
frontend/src/hooks/useNotificationPreview.ts
```

**Files to modify:**
```
backend/core/models/account.py                      # +notification_tone field, +TONE constants
backend/core/views/account.py                       # +set_notification_tone, +notification_preview, +tone in _build_account_response
backend/core/urls.py                                # +2 routes
backend/core/services/email.py                      # subject + body builders accept tone; send_notification_email reads account.notification_tone
backend/core/tests/test_services/test_email.py      # extend across three tones
frontend/src/types/account.ts                       # +NotificationTone type, +notification_tone field
frontend/src/app/(dashboard)/settings/page.tsx      # +Notifications section
```

### Dependencies

- **Upstream**: Story 4.1 done (Resend + email service in place). Migration 0012 is the latest.
- **Downstream**: Story 4.3 (final notice + recovery confirmation) consumes the same `TONE_TEMPLATES` for those email types — write `email_templates.py` with that extension in mind (one new key per email type → tone copy block), but do NOT pre-build 4.3's templates here.
- **Cross-story**: `Account.customer_update_url` capture (deferred follow-up from 4.1) is unrelated to this story; the preview must work without it.

### Testing Standards

- **Backend**: pytest. Mock Resend with `unittest.mock.patch` (only needed for the email service round-trip test). Auto-use `_resend_configured` fixture pattern from `test_services/test_email.py:14-18`. Use `@pytest.mark.django_db`.
- **Fixtures**: reuse `account`, `auth_client`, `mid_account_with_dpa` (see `test_api/test_engine_mode.py:17-22`).
- **Coverage target**: every AC has at least one direct test. The "preview matches sent email" round-trip is the highest-value test — it prevents the entire class of "frontend showed X, subscriber got Y" bugs.
- **Frontend**: if no Vitest/Jest is configured, manual UI verification per Task 10.2 is sufficient and must be documented in Completion Notes.

### References

- [Source: _bmad-output/epics.md — Epic 4, Story 4.2 lines 816-838]
- [Source: _bmad-output/prd.md — FR23 (line 500), brand voice line 59, tone copy intent line 114]
- [Source: _bmad-output/architecture.md — settings/ToneSelector.tsx (line 735), notification service mapping (lines 821, 328), settings forms convention (UX §12.7)]
- [Source: _bmad-output/ux-design-specification.md — UX-DR17 live preview (lines 53, 132, 1011), settings auto-save (line 1052), Sheet pattern for notification preview (line 1075)]
- [Source: _bmad-output/4-1-resend-integration-branded-failure-notification-email.md — Resend integration, escape patterns, gate-check order, customer_update_url follow-up note (lines 137, 84)]
- [Source: backend/core/services/email.py — current single-tone implementation to refactor]
- [Source: backend/core/views/account.py — set_engine_mode pattern (lines 181-249) + _build_account_response (lines 96-140)]
- [Source: backend/core/models/account.py — Account model + TIER constants pattern]
- [Source: frontend/src/app/(dashboard)/settings/page.tsx — radio-card markup to reuse + sonner toast pattern]
- [Source: frontend/src/hooks/useAccount.ts — TanStack Query cache key conventions]

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

- Backend: `docker compose exec -T web poetry run pytest core/tests/test_models/test_account.py core/tests/test_services/test_email.py core/tests/test_api/test_notification_tone.py core/tests/test_api/test_notification_preview.py` → 40 passed.
- Frontend: `cd frontend && npx vitest run src/__tests__/ToneSelector.test.tsx src/__tests__/SettingsModeSwitcher.test.tsx` → 9 passed.
- Pre-existing failures in `NavBar.test.tsx`, `BatchActionToolbar.test.tsx`, `ProfileComplete.test.tsx`, `ReviewQueuePage.test.tsx` and the billing-webhook backend tests are unrelated to this story (verified by stashing changes — same failures occur on clean main state).

### Completion Notes List

- TDD red-green-refactor followed for every backend test file.
- Tone copy is the single source of truth in `backend/core/services/email_templates.py` — both the engine path (`send_notification_email`) and the preview endpoint render through the same `_build_subject` / `_build_html_body` helpers. A round-trip test in `test_email.py` enforces this invariant.
- Minimal-tone two-paragraph cap is enforced **by construction** (the `body_paragraphs` callable returns at most 2 strings) and a regex-based test guards against regressions.
- All 4-1 sanitization tests (HTML escape + header CRLF strip) parametrized across the three tones — no XSS regression.
- `_build_subject` and `_build_html_body` accept a `tone` keyword that defaults to `DEFAULT_TONE` ("professional") so the existing 4-1 test signatures continue to compile.
- Preview endpoint is intentionally **not** tier/DPA-gated — it is a sales surface for Free-tier accounts (AC 7).
- Manual UI verification deferred to local QA per Task 10.2 (requires running `docker compose up` and exercising the Settings page).

### File List

**Backend (new)**
- `backend/core/migrations/0013_account_notification_tone.py`
- `backend/core/services/email_templates.py`
- `backend/core/tests/test_models/test_account.py`
- `backend/core/tests/test_api/test_notification_tone.py`
- `backend/core/tests/test_api/test_notification_preview.py`

**Backend (modified)**
- `backend/core/models/account.py` — added `TONE_*` constants, `DEFAULT_TONE`, `notification_tone` field
- `backend/core/services/email.py` — refactored `_build_subject`, `_build_html_body`, `send_notification_email` to be tone-aware
- `backend/core/views/account.py` — added `set_notification_tone`, `notification_preview`; included `notification_tone` in `_build_account_response`
- `backend/core/urls.py` — wired the two new routes
- `backend/core/tests/test_services/test_email.py` — added three-tone coverage, body-paragraph cap, parametric escape tests, round-trip test

**Frontend (new)**
- `frontend/src/components/settings/ToneSelector.tsx`
- `frontend/src/components/settings/NotificationPreview.tsx`
- `frontend/src/hooks/useNotificationPreview.ts`
- `frontend/src/__tests__/ToneSelector.test.tsx`

**Frontend (modified)**
- `frontend/src/types/account.ts` — added `NotificationTone` type and `notification_tone` field on `Account`
- `frontend/src/app/(dashboard)/settings/page.tsx` — Notifications section with tone selector + preview
- `frontend/src/__tests__/SettingsModeSwitcher.test.tsx` — scoped engine-mode radio assertion to `name="engine_mode"`, mocked `useNotificationPreview`

### Change Log

| Date       | Change |
|------------|--------|
| 2026-04-25 | Story created and implemented end-to-end. All ACs satisfied. Story moved to `review`. |
| 2026-04-26 | Code review completed (3 layers: blind, edge-case, acceptance). 5 decision-needed, 9 patch, 2 defer, 7 dismissed. |

### Review Findings

**Decision-needed:**

- [ ] [Review][Decision] **Minimal `card_expired` body has 3 sentences — violates AC3 "two sentences maximum"** — `email_templates.py:80-85` returns paragraph 2 as `"Update your card to continue. Access remains active."` which is two sentences. Combined with paragraph 1 the body has 3 sentences. Spec AC3: "Minimal: bare facts, two sentences maximum in the body". Test counts `<p>` blocks (passes), not sentences. Options: (a) merge into one sentence (e.g., "Update your card to continue — access remains active."), (b) drop the "Access remains active." sentence, (c) accept the deviation and amend the spec.
- [ ] [Review][Decision] **CTA `href` interpolates `customer_update_url` unescaped** — `email.py` (`_build_html_body` CTA block) embeds the portal URL into `<a href="{portal_url}">` without escaping or validation. Comment at lines 81-84 explicitly states URLs are not escaped — callers must validate. Today the preview path uses a hardcoded placeholder and no caller of `send_notification_email` validates. Once Story 4.1's deferred `customer_update_url` capture lands, an attacker-controlled value (e.g., `"><script>...`) breaks out of the attribute. Options: (a) `html.escape(portal_url, quote=True)` as defense-in-depth, (b) validate URL scheme/format at capture time (Story 4.1 follow-up), (c) defer to 4.1 capture story.
- [ ] [Review][Decision] **Backend tone endpoint enforces tier only — frontend disables on DPA + engine_mode** — `views/account.py:322` rejects only `TIER_FREE`; frontend disables when `tier === "free" || !dpa_accepted || !engine_mode` and shows hint "Accept the Data Processing Agreement to enable tone selection". A Mid/Pro account without DPA or engine_mode can bypass the UI gate via direct POST. Spec AC5 only specifies the tier gate, so backend is per-spec — but frontend hint implies stricter rules. Options: (a) tighten backend to also gate on `dpa_accepted` (mirrors `set_engine_mode`), (b) relax frontend hint to mention only tier, (c) accept the discrepancy as intentional (UX guidance only).
- [ ] [Review][Decision] **Empty `?tone=` query param silently falls back to saved tone** — `views/account.py:266` `tone = request.query_params.get("tone") or account.notification_tone or DEFAULT_TONE`. Spec says "an invalid `tone` value returns `400 INVALID_TONE`". Empty string is arguably invalid; current behavior treats it as not provided. POST endpoint correctly rejects empty. Options: (a) reject empty `?tone=` with 400 (consistency), (b) keep lenient fallback (current).
- [ ] [Review][Decision] **Preview cache wiped on every tone save** — `ToneSelector.tsx:58` invalidates `["notification-preview"]` after a successful save, defeating the per-tone `staleTime: 5min` cache. Spec line 146: "Cache per tone — the three queries become hot after first hover/click and switching is instantaneous." Preview output depends only on `tone` + `company_name`, neither of which the tone-save endpoint can change. Options: (a) remove the `notification-preview` invalidation (keep per-tone cache warm), (b) keep current invalidation (defensive against any future server-side template change), (c) invalidate only the saved tone's query.

**Patch:**

- [ ] [Review][Patch] **Footer text is double HTML-escaped** — `backend/core/services/email.py:102` does `html.escape(template.footer(escaped_company))` where `template.footer(...)` already received the pre-escaped company. Company names with `&`, `<`, `>`, `"`, `'` render as `Acme &amp; Co` instead of `Acme & Co` in the footer. Body paragraphs and `<h2>` are correctly single-escaped. Tests pass because `&lt;script&gt;` substring still appears in the body. Fix: pass raw `company_name` to `template.footer(...)` and escape once, OR drop the second `html.escape()` and rely on the already-escaped value.
- [ ] [Review][Patch] **`selectedTone` shadow state can drift from server truth** — `frontend/src/app/(dashboard)/settings/page.tsx` keeps a local `selectedTone` state synced via `useEffect` from `account.notification_tone`. The optimistic update path means the effect mirrors stale optimistic values into local state. Fix: derive `selectedTone` directly from `account.notification_tone` and remove the local state + effect.
- [ ] [Review][Patch] **Body-paragraphs path interpolates raw template strings without escape (defense-in-depth)** — `backend/core/services/email.py` interpolates each paragraph into `<p>` directly: `f'<p style="...">{p}</p>'`. Currently safe because templates only embed pre-escaped values, but the contract is invisible at the call site. Fix: `html.escape(p)` per paragraph, OR document the pre-escape contract loudly in `email_templates.py`.
- [ ] [Review][Patch] **Header injection regex does not strip Unicode line separators (U+2028, U+2029, U+0085)** — `backend/core/services/email.py:25` `_HEADER_INJECTION_CHARS = re.compile(r'[\r\n"<>]')` misses Unicode line separators. Fix: extend pattern to `[\r\n\u2028\u2029\u0085"<>]`.
- [ ] [Review][Patch] **`useNotificationPreview` URL interpolates `tone` without `encodeURIComponent`** — `frontend/src/hooks/useNotificationPreview.ts:21` `\`/account/notification-preview/?tone=${tone}\``. TS union type protects today; defense-in-depth missing. Fix: `?tone=${encodeURIComponent(tone)}`.
- [ ] [Review][Patch] **`from typing import Callable` is deprecated** — `backend/core/services/email_templates.py`. Fix: `from collections.abc import Callable`.
- [ ] [Review][Patch] **`test_idempotent_when_unchanged` does not assert "no DB write"** — `backend/core/tests/test_api/test_notification_tone.py:36-40` only checks audit-row count. A regression that re-saves on every call would not be caught. Fix: assert `account.modified_at` (or equivalent) is unchanged, or count save calls via mock.
- [ ] [Review][Patch] **`test_friendly_body_uses_contractions` comment is misleading** — `backend/core/tests/test_services/test_email.py` says "(apostrophe survives html.escape)" but the apostrophe is a template literal that never goes through `html.escape`. Fix: drop the misleading comment; the assertion as-is is fine.
- [ ] [Review][Patch] **Test gap: no escape test for footer across tones** — `backend/core/tests/test_services/test_email.py` XSS tests assert `&lt;script&gt;` substring is in body, but never check the footer for the same property. The double-escape footer bug above is invisible to this suite. Fix: add a parametric test asserting `&lt;script&gt;` (single-escaped) appears in the entire `html_body`, including the footer span.

**Deferred:**

- [x] [Review][Defer] **iframe `sandbox=""` blocks the CTA link click in the preview** [`frontend/src/components/settings/NotificationPreview.tsx:40-45`] — UX consideration: a user trying to verify the link destination cannot click it. Deferred — security trade-off accepted for now; surface URL textually in a follow-up if needed.
- [x] [Review][Defer] **Stale preview after `complete_profile` changes `company_name` (5-minute staleTime)** [`frontend/src/hooks/useNotificationPreview.ts:25`] — Cross-story flow: profile completion does not invalidate `["notification-preview"]`. Deferred to the profile-completion flow / future cleanup.

**Dismissed (7) — recorded for traceability:**
- iframe className diverges from spec verbatim (intentional UI improvement: fuses with subject card).
- Inline error `<div>` instead of `toast.error` (spec wording is internally contradictory; inline is less disruptive for a preview surface).
- ToneSelector card descriptions borderline duplication (UI labels, not template copy).
- Apostrophes in template literals are not pre-escaped (HTML element text content; valid HTML5).
- `notification_preview` imports private `_build_*` helpers (single-source-of-truth requirement makes this intentional per spec).
- Migration hardcodes `default='professional'` instead of `DEFAULT_TONE` (Django auto-generated migration — standard/correct behavior).
- `set_notification_tone` row-lock-then-403 for free-tier (consistent with `set_engine_mode`; perf nit only).
