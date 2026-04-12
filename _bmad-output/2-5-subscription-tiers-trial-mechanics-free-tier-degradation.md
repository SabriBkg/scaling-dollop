# Story 2.5: Subscription Tiers, Trial Mechanics & Free-Tier Degradation

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a founder,
I want SafeNet to manage my trial period automatically and clearly communicate my tier status and limitations,
so that I understand what I have access to and can upgrade when ready.

## Acceptance Criteria

1. **Given** a new account is created via Stripe Connect **When** the account is provisioned **Then** it is placed on a 30-day Mid-tier trial with full engine access and no payment method required (FR35) **And** polling runs at hourly frequency during the trial period

2. **Given** a trial account reaches day 30 without upgrading **When** the trial expiration job runs **Then** the account is automatically downgraded to Free tier (FR36) **And** polling frequency drops to twice-monthly **And** the dashboard displays the degradation prominently: "Your next scan is in X days" (FR37) **And** the recovery engine is deactivated — no new retries or notifications are sent

3. **Given** a Free-tier client views their dashboard **When** the tier indicator is rendered **Then** the "estimated recoverable revenue" figure remains visible and accurate (permanent Free-tier feature) **And** a single upgrade CTA is anchored below it (FR39) **And** the next scan countdown is visible without scrolling (FR37)

4. **Given** a client clicks the upgrade CTA and completes Stripe Billing checkout **When** the subscription is confirmed via Stripe webhook **Then** the account is immediately upgraded to Mid tier **And** hourly polling resumes **And** the engine activation flow (DPA + mode selection) is presented if not previously completed

## Tasks / Subtasks

- [x] Task 1: Backend — `services/tier.py` Tier Gating Service (AC: #1, #2)
  - [x] 1.1 Create `core/services/tier.py` with tier gating functions
  - [x] 1.2 `get_polling_frequency(account) -> int` — returns seconds between polls: 3600 for Mid/Pro, 1_296_000 (15 days) for Free
  - [x] 1.3 `is_engine_active(account) -> bool` — True only for Mid/Pro tiers (not Free)
  - [x] 1.4 `check_and_degrade_trial(account) -> bool` — if `is_on_trial` is False AND `tier == TIER_MID` AND `trial_ends_at` is in the past, downgrade to `TIER_FREE`, return True
  - [x] 1.5 `upgrade_to_mid(account) -> None` — set `tier = TIER_MID`, clear `trial_ends_at`, save
  - [x] 1.6 Write tests in `core/tests/test_services/test_tier.py`

- [x] Task 2: Backend — Trial Expiration Celery Beat Job (AC: #2)
  - [x] 2.1 Create `core/tasks/trial_expiration.py` with `expire_trials` task
  - [x] 2.2 Query: `Account.objects.filter(tier=TIER_MID, trial_ends_at__lte=timezone.now())` — all expired trials
  - [x] 2.3 For each: set `tier = TIER_FREE`, write audit event `trial_expired` with `outcome="success"`
  - [x] 2.4 Register in `safenet_backend/celery.py` beat_schedule: `"daily-trial-expiration"` running every 24 hours (86400s)
  - [x] 2.5 Write tests in `core/tests/test_tasks/test_trial_expiration.py`

- [x] Task 3: Backend — Tier-Gated Polling (AC: #1, #2)
  - [x] 3.1 Modify `core/tasks/polling.py` `poll_account_failures` — add tier check at start
  - [x] 3.2 If `account.tier == TIER_FREE`: check `get_polling_frequency()` against last poll timestamp; skip if not due
  - [x] 3.3 Audit log `polling_skipped_free_tier` when skipping a Free account
  - [x] 3.4 Update existing polling tests + add Free-tier skip test

- [x] Task 4: Backend — Stripe Billing Webhook Handler (AC: #4)
  - [x] 4.1 Create `core/views/billing.py` with `stripe_billing_webhook` view
  - [x] 4.2 Verify webhook signature using `stripe.Webhook.construct_event()` with `STRIPE_WEBHOOK_SECRET` env var
  - [x] 4.3 Handle `checkout.session.completed` event: look up Account by `client_reference_id`, call `upgrade_to_mid(account)`
  - [x] 4.4 Handle `customer.subscription.deleted` event: downgrade account to Free
  - [x] 4.5 Return 200 for unhandled event types (Stripe best practice)
  - [x] 4.6 Wire endpoint: `path("v1/billing/webhook/", stripe_billing_webhook, name="stripe_billing_webhook")` — exempt from JWT auth and CSRF
  - [x] 4.7 Write tests in `core/tests/test_api/test_billing_webhook.py`

- [x] Task 5: Backend — Stripe Checkout Session Endpoint (AC: #4)
  - [x] 5.1 Create `create_checkout_session` view in `core/views/billing.py`
  - [x] 5.2 Authenticated endpoint `POST /api/v1/billing/checkout/` — creates Stripe Checkout Session
  - [x] 5.3 Set `client_reference_id` to `account.id` for webhook correlation
  - [x] 5.4 Set `success_url` and `cancel_url` pointing to frontend dashboard
  - [x] 5.5 Price: use `STRIPE_MID_TIER_PRICE_ID` env var (Stripe Price object for Mid tier at EUR 29/month)
  - [x] 5.6 Wire endpoint and write tests

- [x] Task 6: Backend — Account Detail Endpoint Enhancements (AC: #2, #3)
  - [x] 6.1 Add `trial_days_remaining` computed field to `account_detail` response — `max(0, (trial_ends_at - now).days)` if on trial, else `null`
  - [x] 6.2 Add `next_scan_at` computed field — based on last poll timestamp + `get_polling_frequency(account)`, or `null` if Mid/Pro (hourly, no need to show)
  - [x] 6.3 Add `engine_active` computed field from `is_engine_active(account)`
  - [x] 6.4 Update existing account detail tests

- [x] Task 7: Frontend — Account Type Extensions (AC: #2, #3)
  - [x] 7.1 Update `src/types/account.ts` — add `trial_days_remaining: number | null`, `next_scan_at: string | null`, `engine_active: boolean`
  - [x] 7.2 No changes needed to `useAccount` hook — fields come from same endpoint

- [x] Task 8: Frontend — `TierBadge` Component (AC: #2, #3)
  - [x] 8.1 Create `src/components/settings/TierBadge.tsx`
  - [x] 8.2 Display current tier as pill badge: "Free" (grey), "Mid — Trial (X days left)" (blue), "Mid" (blue), "Pro" (purple)
  - [x] 8.3 Use design tokens: `--text-secondary` for Free, `--accent-active` for Mid, `--accent-recovery` for Pro

- [x] Task 9: Frontend — `NextScanCountdown` Component (AC: #2, #3)
  - [x] 9.1 Create `src/components/dashboard/NextScanCountdown.tsx`
  - [x] 9.2 For Free-tier: render "Your next scan is in X days" prominently (FR37) using `next_scan_at` from account
  - [x] 9.3 Position above StoryArcPanel in dashboard — visible without scrolling
  - [x] 9.4 For Mid/Pro: do not render (hourly polling, no countdown needed)

- [x] Task 10: Frontend — Upgrade Flow via Stripe Checkout (AC: #4)
  - [x] 10.1 Modify `src/components/dashboard/UpgradeCTA.tsx` — `onClick` calls `POST /api/v1/billing/checkout/` and redirects to `session.url`
  - [x] 10.2 Add loading state while checkout session is created
  - [x] 10.3 Handle error (toast or inline message)
  - [x] 10.4 On success return from Stripe, `useAccount` refetch should reflect new tier

- [x] Task 11: Frontend — Settings Page Subscription Section (AC: #4)
  - [x] 11.1 Update `src/app/(dashboard)/settings/page.tsx` with subscription management section
  - [x] 11.2 Show `TierBadge`, trial status, and upgrade button (if Free)
  - [x] 11.3 For paid Mid: show "Manage subscription" link (Stripe Customer Portal or placeholder)

- [x] Task 12: Frontend — Dashboard Integration (AC: #2, #3)
  - [x] 12.1 Add `NextScanCountdown` to dashboard page (above StoryArcPanel, Free tier only)
  - [x] 12.2 Ensure `UpgradeCTA` still renders correctly with new checkout flow
  - [x] 12.3 Write/update frontend tests for tier-conditional rendering

## Dev Notes

### Architecture Compliance

- **Tier service location:** `core/services/tier.py` — specified in architecture [Source: architecture.md#Cross-cutting concerns table]
- **Billing view location:** `core/views/billing.py` — specified in architecture gap analysis [Source: architecture.md#Validation & Gap Analysis]
- **Billing webhook route:** `/api/v1/billing/webhook/` — specified in architecture [Source: architecture.md#Validation & Gap Analysis]
- **Frontend component locations:** `src/components/dashboard/` for dashboard components, `src/components/settings/` for settings components [Source: architecture.md#Component Organization]
- **API response envelope:** Must use `{data: {...}}` format — never bare root objects [Source: architecture.md#API Response Envelope]
- **Monetary values:** Integer cents in API, formatted in frontend via `formatCurrency` from `src/lib/formatters.ts` [Source: architecture.md#Monetary Values]
- **Tenant isolation:** All queries must scope to `account_id` — use `request.user.account` pattern [Source: architecture.md#Tenant Isolation]
- **Audit trail:** All tier transitions must use `write_audit_event()` from `core/services/audit.py` [Source: architecture.md#Cross-cutting concerns]

### Technical Requirements

- **Existing Account model fields:** `tier` (CharField: free/mid/pro) and `trial_ends_at` (DateTimeField, nullable) already exist in `core/models/account.py` with migration `0002_account_tier_trial.py` — DO NOT create new migrations for these fields
- **Existing `is_on_trial` property:** `account.py:56-58` — returns True if `tier == TIER_MID` AND `trial_ends_at` is in the future. Reuse this, do not recreate
- **Existing trial initialization:** `core/views/stripe.py` already sets `tier=TIER_MID` and `trial_ends_at=now()+30days` on OAuth callback — AC1 is already implemented, just verify
- **Existing UpgradeCTA component:** `src/components/dashboard/UpgradeCTA.tsx` exists (renders for `tier === "free"` only) — extend it with checkout onClick, DO NOT create a new component
- **Existing Celery beat config:** `safenet_backend/celery.py:13-18` has `beat_schedule` dict with `hourly-retry-poll` — add new entries to this dict
- **Existing polling task:** `core/tasks/polling.py` polls ALL StripeConnection accounts — must add tier-based frequency gating
- **Existing account_detail endpoint:** `core/views/account.py` returns tier info — extend response, do not create new endpoint
- **Existing useAccount hook:** `src/hooks/useAccount.ts` fetches `/account/me/` — no changes needed, just update TypeScript types
- **Existing dashboard page:** `src/app/(dashboard)/dashboard/page.tsx` already imports `UpgradeCTA` and passes it as `column2Footer` to `StoryArcPanel`
- **Settings page:** `src/app/(dashboard)/settings/page.tsx` is a placeholder — ready to build out

### Stripe Billing Integration Notes

- **SafeNet uses Stripe Billing for its own subscriptions** — dogfooding the ecosystem [Source: architecture.md#Technical Stack]
- **Stripe SDK version:** `stripe ^15.0.1` in `pyproject.toml` — use `stripe.checkout.Session.create()` and `stripe.Webhook.construct_event()`
- **CRITICAL:** Stripe SDK v15 moved exceptions to `stripe.StripeError` (not `stripe.error.StripeError`) — use `stripe.StripeError` for all exception handling [Source: deferred-work.md]
- **Webhook security:** Verify signature with `STRIPE_WEBHOOK_SECRET` env var. Webhook endpoint must be exempt from JWT authentication AND CSRF protection
- **Checkout flow:** Create Stripe Checkout Session server-side, redirect client to `session.url`, Stripe redirects back on completion. Webhook confirms payment
- **Environment variables needed:** `STRIPE_WEBHOOK_SECRET`, `STRIPE_MID_TIER_PRICE_ID` — document in .env.example
- **Idempotency:** Webhook events can be delivered multiple times — check if account is already on the correct tier before making changes

### Polling Frequency Architecture

- **Mid/Pro tier:** Hourly (3600s) — existing beat schedule handles this
- **Free tier:** Twice-monthly (~15 days = 1,296,000s) — not a separate beat entry. Instead, the existing hourly `poll_new_failures` dispatches for ALL accounts, and `poll_account_failures` checks the tier + last poll timestamp to skip Free accounts that aren't due
- **Rationale:** Single beat entry for polling, tier logic inside the per-account task. Simpler than managing per-tier beat schedules

### Previous Story Intelligence (Story 2.4)

- **Dashboard API caching:** `dashboard_summary_{account_id}` key with 5-min TTL in Redis — invalidate this cache after tier change so dashboard reflects new state immediately
- **UpgradeCTA positioning:** Already inside StoryArcPanel Column 2 via `column2Footer` prop — maintain this placement
- **Testing pattern:** Use `@pytest.mark.django_db`, DRF `APIClient`, factory-based test data. Frontend tests: Vitest + React Testing Library with `vi.mock` for hooks
- **Debug lesson:** Multiple `vi.mock()` calls in same file can conflict — use `mockReturnValue` pattern with `beforeEach` reset
- **Review findings applied:** `prefers-reduced-motion` CSS rule exists in `globals.css`, KPI numbers have `tabIndex={0}` and `role="text"`

### Known Deferred Issues (DO NOT fix in this story, but be aware)

- `initiate_stripe_connect` has no rate limiting — tracked in deferred-work.md
- `stripe.error.StripeError` vs `stripe.StripeError` in existing `views/stripe.py:93` — use correct `stripe.StripeError` in NEW code
- `useAccount` query fires without auth gate — may cause 401 on unauthenticated loads
- `toLocaleString()` locale-dependent formatting — pre-existing pattern

### Project Structure Notes

- Backend: `backend/core/services/tier.py` (new), `backend/core/views/billing.py` (new), `backend/core/tasks/trial_expiration.py` (new)
- Backend modified: `backend/core/tasks/polling.py`, `backend/core/views/account.py`, `backend/core/urls.py`, `backend/safenet_backend/celery.py`
- Frontend: `src/components/settings/TierBadge.tsx` (new), `src/components/dashboard/NextScanCountdown.tsx` (new)
- Frontend modified: `src/components/dashboard/UpgradeCTA.tsx`, `src/types/account.ts`, `src/app/(dashboard)/settings/page.tsx`, `src/app/(dashboard)/dashboard/page.tsx`
- Tests: `core/tests/test_services/test_tier.py`, `core/tests/test_tasks/test_trial_expiration.py`, `core/tests/test_api/test_billing_webhook.py`, frontend Vitest files

### References

- [Source: architecture.md#Cross-cutting concerns] — tier.py location and tier gating pattern
- [Source: architecture.md#Validation & Gap Analysis] — billing.py and webhook endpoint requirement
- [Source: architecture.md#Technical Stack] — Stripe Billing for SafeNet's own subscriptions
- [Source: prd.md#FR35-FR39] — Trial mechanics, degradation, upgrade CTA requirements
- [Source: ux-design-specification.md#Journey 1] — Trial activation as low-ceremony switch, upgrade CTA anchored to recoverable revenue
- [Source: ux-design-specification.md#Key Design Challenges] — "Free tier as ROI calculator, not locked preview"
- [Source: epics.md#Story 2.5] — Full acceptance criteria and BDD scenarios
- [Source: deferred-work.md] — Stripe SDK v15 exception path, rate limiting gaps

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Pre-existing ProfileComplete.test.tsx failures (4 tests) — caused by missing QueryClientProvider in test setup, not related to this story

### Completion Notes List

- Task 1: Created `core/services/tier.py` with 5 tier gating functions (`get_polling_frequency`, `is_engine_active`, `check_and_degrade_trial`, `upgrade_to_mid`) plus 11 unit tests
- Task 2: Created `core/tasks/trial_expiration.py` with `expire_trials` Celery task, registered at 86400s (daily) in beat_schedule, 5 tests
- Task 3: Added Free-tier frequency gating to `poll_account_failures` — skips when not due, writes `polling_skipped_free_tier` audit event, 3 new tests (all 11 polling tests pass)
- Task 4: Created `stripe_billing_webhook` view — handles `checkout.session.completed` (upgrade) and `customer.subscription.deleted` (downgrade), signature verification, 6 tests
- Task 5: Created `create_checkout_session` view — authenticated POST creates Stripe Checkout Session with `client_reference_id` for correlation, 3 tests
- Task 6: Extended `account_detail` response with `trial_days_remaining`, `next_scan_at`, `engine_active` computed fields, 4 new tests
- Task 7: Extended Account TypeScript type with new computed fields
- Task 8: Created `TierBadge` component — pill badge with tier-specific colors using design tokens, 4 tests
- Task 9: Created `NextScanCountdown` component — renders "Your next scan is in X days" for Free tier only, 3 tests
- Task 10: Extended `UpgradeCTA` with checkout flow — POST to billing/checkout, loading state, error handling
- Task 11: Built out Settings page with subscription section — TierBadge, trial status, upgrade CTA
- Task 12: Integrated `NextScanCountdown` above StoryArcPanel on dashboard page
- All 192 backend tests pass, 41 frontend tests pass (4 pre-existing failures in ProfileComplete unrelated to this story)
- Dashboard cache (`dashboard_summary_{account_id}`) invalidated on tier changes for immediate UI reflection
- Used correct `stripe.StripeError` (not `stripe.error.StripeError`) in new code per SDK v15

### Change Log

- 2026-04-12: Story 2.5 implementation complete — subscription tiers, trial mechanics, free-tier degradation, Stripe Billing integration

### File List

New files:
- backend/core/services/tier.py
- backend/core/tasks/trial_expiration.py
- backend/core/views/billing.py
- backend/core/tests/test_services/__init__.py
- backend/core/tests/test_services/test_tier.py
- backend/core/tests/test_tasks/test_trial_expiration.py
- backend/core/tests/test_api/test_billing_webhook.py
- frontend/src/components/settings/TierBadge.tsx
- frontend/src/components/dashboard/NextScanCountdown.tsx
- frontend/src/__tests__/TierBadge.test.tsx
- frontend/src/__tests__/NextScanCountdown.test.tsx

Modified files:
- backend/core/tasks/polling.py (added Free-tier frequency gating)
- backend/core/views/account.py (added computed fields)
- backend/core/urls.py (added billing endpoints)
- backend/safenet_backend/celery.py (added daily-trial-expiration beat)
- backend/core/tests/test_tasks/test_polling.py (added 3 Free-tier tests)
- backend/core/tests/test_api/test_profile.py (added 4 tier field tests)
- frontend/src/types/account.ts (added new fields)
- frontend/src/components/dashboard/UpgradeCTA.tsx (added checkout flow)
- frontend/src/app/(dashboard)/settings/page.tsx (built out subscription section)
- frontend/src/app/(dashboard)/dashboard/page.tsx (added NextScanCountdown)
