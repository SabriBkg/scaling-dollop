# Story 3.1: DPA Acceptance & Engine Mode Selection Flow

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mid-tier founder,
I want to review and formally accept the Data Processing Agreement, then choose my recovery mode,
so that I understand what SafeNet processes on my behalf and explicitly authorize the engine to act.

## Acceptance Criteria

1. **Given** a Mid-tier client clicks "Activate recovery engine" **When** the DPA screen is presented **Then** a full-page formal DPA screen is shown (not a checkbox, not a modal) documenting: what SafeNet processes, on whose behalf, for what purpose, retention policy, security measures (FR3, UX-DR15)

2. **Given** a client reviews the DPA **When** they click "I accept and sign" **Then** a DPAAcceptance record is created with timestamp + account FK **And** an audit event `dpa_accepted` is written with actor="client", outcome="success"

3. **Given** a client accepts the DPA **When** the DPA is recorded **Then** they advance to the mode selection screen (engine does NOT activate yet)

4. **Given** a client is on the mode selection screen **When** both options are displayed **Then** Autopilot is described as: "SafeNet handles all recovery automatically — no action required from you" **And** Supervised is described as: "SafeNet queues actions for your review before executing" **And** each option shows plain-language consequence statements

5. **Given** a client selects a mode and confirms **When** the mode is saved **Then** the recovery engine activates, `EngineStatusIndicator` updates in the NavBar **And** an audit event `engine_activated` is written with metadata `{mode: "autopilot"|"supervised"}`

6. **Given** a client has previously accepted the DPA **When** they visit Settings **Then** they can switch between Autopilot and Supervised modes without re-signing the DPA (FR5) **And** an audit event `engine_mode_switched` is written with metadata `{from: "...", to: "..."}`

7. **Given** a client exits the DPA screen without accepting **When** they return to the dashboard **Then** they remain on their current tier with engine inactive **And** a non-intrusive reminder is shown on next login encouraging activation

## Tasks / Subtasks

### Backend

- [x] Task 1: Database — Add DPA & engine mode fields to Account model (AC: #2, #5)
  - [x]1.1 Add `dpa_accepted_at` (DateTimeField, nullable, blank=True) to Account model
  - [x]1.2 Add `engine_mode` (CharField, max_length=20, choices=["autopilot", "supervised"], nullable, blank=True) to Account model
  - [x]1.3 Add `dpa_accepted` property (bool) — returns `self.dpa_accepted_at is not None`
  - [x]1.4 Create migration `0006_add_dpa_engine_mode_to_account.py`

- [x]Task 2: Backend — DPA Acceptance Endpoint (AC: #1, #2, #3)
  - [x]2.1 Create `accept_dpa` view in `core/views/account.py`
  - [x]2.2 Authenticated POST `/api/v1/account/dpa/accept/` — sets `dpa_accepted_at = timezone.now()` with `select_for_update()` row lock
  - [x]2.3 Validate: account must be Mid or Pro tier (not Free)
  - [x]2.4 Idempotency: if already accepted, return 200 with existing data (do not overwrite timestamp)
  - [x]2.5 Write audit event via `write_audit_event(subscriber=None, actor="client", action="dpa_accepted", outcome="success", account=account)`
  - [x]2.6 Return full account detail response (same envelope as `account_detail`)
  - [x]2.7 Wire URL: `path("v1/account/dpa/accept/", accept_dpa, name="accept_dpa")`
  - [x]2.8 Write tests in `core/tests/test_api/test_dpa.py`

- [x]Task 3: Backend — Engine Mode Selection Endpoint (AC: #5, #6)
  - [x]3.1 Create `set_engine_mode` view in `core/views/account.py`
  - [x]3.2 Authenticated POST `/api/v1/account/engine/mode/` — accepts `{"mode": "autopilot"|"supervised"}`
  - [x]3.3 Hard gate: DPA must be accepted (`account.dpa_accepted` must be True), else return 403 with message
  - [x]3.4 First-time activation: if `engine_mode` was null, write `engine_activated` audit event with metadata `{mode: "..."}`
  - [x]3.5 Mode switch: if `engine_mode` was not null and different, write `engine_mode_switched` audit event with metadata `{from: "...", to: "..."}`
  - [x]3.6 Same mode: return 200 without changes (idempotent)
  - [x]3.7 Use `select_for_update()` row lock for concurrency safety
  - [x]3.8 Invalidate dashboard cache: `cache.delete(f"dashboard_summary_{account.id}")`
  - [x]3.9 Return full account detail response
  - [x]3.10 Wire URL: `path("v1/account/engine/mode/", set_engine_mode, name="set_engine_mode")`
  - [x]3.11 Write tests in `core/tests/test_api/test_engine_mode.py`

- [x]Task 4: Backend — Update `is_engine_active()` and Account Detail (AC: #5, #7)
  - [x]4.1 Modify `core/services/tier.py` `is_engine_active(account)` — now returns `True` only when: tier is Mid or Pro AND `account.dpa_accepted` is True AND `account.engine_mode` is not None
  - [x]4.2 Add `dpa_accepted` (bool), `dpa_accepted_at` (ISO string or null), `engine_mode` (string or null) to `account_detail` response in `core/views/account.py`
  - [x]4.3 Update existing account detail tests for new fields
  - [x]4.4 Update `complete_profile` response to include new fields

### Frontend

- [x]Task 5: Frontend — Extend Account Type & Hook (AC: all)
  - [x]5.1 Add to `src/types/account.ts`: `dpa_accepted: boolean`, `dpa_accepted_at: string | null`, `engine_mode: "autopilot" | "supervised" | null`
  - [x]5.2 No changes needed to `useAccount` hook — fields come from same `/account/me/` endpoint

- [x]Task 6: Frontend — DPA Acceptance Full-Page Screen (AC: #1, #2, #3, #7)
  - [x]6.1 Create `src/app/(dashboard)/activate/page.tsx` — full-page DPA screen
  - [x]6.2 Render DPA content: what SafeNet processes, on whose behalf, for what purpose, retention policy, security measures
  - [x]6.3 "I accept and sign" button — POST `/api/proxy/account/dpa/accept/`
  - [x]6.4 On success: navigate to `/activate/mode` (mode selection)
  - [x]6.5 "Go back" link — returns to dashboard without accepting
  - [x]6.6 Loading + error states with toast on failure
  - [x]6.7 If DPA already accepted, redirect to `/activate/mode` or dashboard

- [x]Task 7: Frontend — Mode Selection Screen (AC: #3, #4, #5)
  - [x]7.1 Create `src/app/(dashboard)/activate/mode/page.tsx` — mode selection screen
  - [x]7.2 Two option cards: Autopilot and Supervised with plain-language consequence descriptions
  - [x]7.3 Autopilot card: "SafeNet handles all recovery automatically — no action required from you"
  - [x]7.4 Supervised card: "SafeNet queues actions for your review before executing"
  - [x]7.5 "Confirm and activate" button — POST `/api/proxy/account/engine/mode/` with `{mode: selected}`
  - [x]7.6 On success: invalidate `["account", "me"]` query cache, navigate to dashboard
  - [x]7.7 Guard: if DPA not accepted, redirect to `/activate`
  - [x]7.8 Guard: if engine already active (mode already set), redirect to dashboard

- [x]Task 8: Frontend — Update `useEngineStatus` Hook (AC: #5)
  - [x]8.1 Replace stub in `src/hooks/useEngineStatus.ts` — derive status from `useAccount()` data
  - [x]8.2 Logic: if `account.engine_mode` is null → status is `"paused"`; else → status is `account.engine_mode`
  - [x]8.3 `last_scan_at` and `next_scan_at` from dashboard summary (keep existing pattern if available, else null)
  - [x]8.4 This makes `EngineStatusIndicator` and NavBar "Review Queue" tab work automatically

- [x]Task 9: Frontend — Dashboard Activation CTA & Reminder (AC: #7)
  - [x]9.1 Modify `UpgradeCTA` or add new `ActivateEngineCTA` component for Mid-tier users who haven't accepted DPA
  - [x]9.2 Condition: `account.tier !== "free" && !account.dpa_accepted` → show "Activate recovery engine" CTA linking to `/activate`
  - [x]9.3 Non-intrusive reminder: subtle banner below KPIs encouraging activation
  - [x]9.4 When DPA is accepted and engine active, CTA disappears

- [x] Task 10: Frontend — Settings Mode Switcher (AC: #6)
  - [x]10.1 Add "Recovery Mode" section to `src/app/(dashboard)/settings/page.tsx`
  - [x]10.2 Show current mode with radio/toggle selector (Autopilot vs Supervised)
  - [x]10.3 On change: POST `/api/proxy/account/engine/mode/` with new mode
  - [x]10.4 Success toast: "Recovery mode updated to {mode}"
  - [x]10.5 Only show section if `account.dpa_accepted` is true
  - [x]10.6 Invalidate `["account", "me"]` query cache on success

- [x] Task 11: Frontend — Tests (AC: all)
  - [x]11.1 Write Vitest tests for DPA acceptance page (render, accept flow, redirect)
  - [x]11.2 Write Vitest tests for Mode selection page (render, selection, activation)
  - [x]11.3 Write Vitest tests for useEngineStatus hook behavior
  - [x]11.4 Write Vitest tests for Settings mode switcher
  - [x]11.5 Write Vitest tests for ActivateEngineCTA conditional rendering

## Dev Notes

### Architecture Compliance

- **Account model extension:** Add fields directly to `core/models/account.py` — Account model is at `backend/core/models/account.py:19-59` [Source: architecture.md#Data Model]
- **View location:** Add new endpoints to `core/views/account.py` — DPA and mode are account-level operations, not separate domains [Source: architecture.md#API Design]
- **API response envelope:** Must use `{data: {...}}` format — never bare root objects [Source: architecture.md#API Response Envelope]
- **Monetary values:** Integer cents in API, formatted in frontend via `formatCurrency` from `src/lib/formatters.ts` [Source: architecture.md#Monetary Values]
- **Tenant isolation:** All queries must scope to `request.user.account` [Source: architecture.md#Tenant Isolation]
- **Audit trail:** All state changes via `write_audit_event()` from `core/services/audit.py` [Source: architecture.md#Cross-cutting concerns]
- **Frontend routing:** New pages go under `src/app/(dashboard)/` to inherit the dashboard layout with NavBar [Source: architecture.md#Component Organization]

### Technical Requirements

- **Existing Account model fields (DO NOT recreate):** `tier` (free/mid/pro), `trial_ends_at`, `company_name`, `owner`, `created_at`, `is_on_trial` property, `profile_complete` property — see `backend/core/models/account.py:19-59`
- **Existing `is_engine_active()`:** `core/services/tier.py:23-25` — currently `return account.tier in (TIER_MID, TIER_PRO)`. Must be updated to ALSO require `account.dpa_accepted` and `account.engine_mode is not None`
- **Existing EngineStatusIndicator:** `src/components/common/EngineStatusIndicator.tsx` — already renders autopilot/supervised/paused/error states with proper colors. No changes needed to this component
- **Existing NavBar:** `src/components/common/NavBar.tsx` — already conditionally shows "Review Queue" tab when `engineStatus.mode === "supervised"`. Will work automatically once `useEngineStatus` is updated
- **Existing useEngineStatus hook (STUB):** `src/hooks/useEngineStatus.ts` — returns hardcoded `"paused"`. Must replace with logic derived from `useAccount()` data
- **Existing `select_for_update()` pattern:** Used in `complete_profile` view (`core/views/account.py`) and `stripe_billing_webhook` — follow same pattern for DPA/mode endpoints
- **Existing dashboard cache pattern:** Cache key `dashboard_summary_{account_id}` with 5-min TTL — invalidate on engine mode changes
- **Existing UpgradeCTA:** `src/components/dashboard/UpgradeCTA.tsx` — renders for `tier === "free"` only. For Mid-tier without DPA, a new/separate CTA is needed
- **Latest migration:** `0005_add_company_name_to_account.py` — next migration is `0006`
- **Models __init__.py:** Currently exports `Account`, `StripeConnection`, `AuditLog`, `Subscriber`, `SubscriberFailure` — no new model file needed (fields go on Account)

### Stripe SDK Notes

- **Stripe SDK v15:** Use `stripe.StripeError` (not `stripe.error.StripeError`) for exception handling [Source: deferred-work.md]
- No Stripe API calls needed for this story — DPA and mode are SafeNet-internal state, not Stripe operations

### Frontend Architecture Notes

- **API calls go through proxy:** All frontend calls use `/api/proxy/...` which proxies to Django backend, adding JWT from httpOnly cookie [Source: `src/app/api/proxy/[...path]/route.ts`]
- **React Query cache keys:** Use `queryClient.invalidateQueries({queryKey: ["account", "me"]})` after DPA/mode changes to refresh account state
- **Design tokens for DPA page:** Use `--bg-surface` for card backgrounds, `--text-primary`/`--text-secondary` for text hierarchy, `--cta` for accept button [Source: `src/app/globals.css`]
- **Toast notifications:** Use `toast.success()` / `toast.error()` from `sonner` — already in the project [Source: package.json]
- **Icon library:** `lucide-react` — use `Shield`, `Zap`, `Eye` or similar icons for DPA/mode selection
- **Component primitives:** `@base-ui/react` Dialog, Button, Card available in `src/components/ui/`
- **Testing pattern:** Vitest + React Testing Library with `vi.mock` for hooks, `QueryClientProvider` wrapper required in tests

### Previous Story Intelligence (Story 2.5)

- **Dashboard cache invalidation:** Must `cache.delete(f"dashboard_summary_{account.id}")` when engine activates or mode switches — learned from Story 2.5 where tier changes didn't reflect immediately
- **Idempotency pattern:** Check current state before writing (e.g., DPA already accepted → return 200, don't overwrite timestamp) — pattern from Story 2.5 webhook handler
- **`select_for_update()` for race conditions:** Applied to prevent concurrent DPA acceptance + trial expiration race — learned from Story 2.5 review
- **Account detail response consistency:** All account-mutating endpoints must return the same full response shape as `account_detail` — pattern from `complete_profile` and billing endpoints
- **Testing pattern:** `@pytest.mark.django_db`, DRF `APIClient`, factory-based test data. Frontend: Vitest + RTL with `vi.mock` for hooks and `beforeEach` reset

### Deferred Work to be Aware Of (DO NOT fix in this story)

- **Engine activation flow post-upgrade:** Story 2.5 deferred wiring the DPA/mode flow after Stripe upgrade (deferred-work.md, line 54). This story creates the flow — but the post-upgrade redirect to `/activate` should be wired as part of this story if upgrading from Free to Mid
- **`useAccount` query fires without auth gate:** May cause 401 on unauthenticated loads — pre-existing, don't fix
- **`stripe.error.StripeError` in views/stripe.py:93:** Pre-existing wrong import — don't touch
- **Free-tier polling gate Redis TTL issue:** Pre-existing — don't fix

### UX Design Requirements

- **DPA is a full-page formal screen** — NOT a checkbox, NOT a modal. Explicit signature/acceptance required (UX-DR15)
- **DPA content sections:** Data processed, purpose, retention policy, security measures, on whose behalf
- **Mode selection:** Two clear option cards with plain-language consequences — NOT a configuration screen
- **Supervised empowers, Autopilot disappears:** Supervised is batch review tool (UX-DR16), Autopilot runs silently
- **Desktop-first:** DPA signing and mode selection are desktop-only complex actions (UX-DR14)
- **Recovery is the hero, not the engine:** Frame DPA in terms of what gets recovered, not technical operations

### Project Structure Notes

**New files to create:**
- `frontend/src/app/(dashboard)/activate/page.tsx` (DPA acceptance page)
- `frontend/src/app/(dashboard)/activate/mode/page.tsx` (mode selection page)
- `backend/core/tests/test_api/test_dpa.py` (DPA endpoint tests)
- `backend/core/tests/test_api/test_engine_mode.py` (engine mode endpoint tests)

**Files to modify:**
- `backend/core/models/account.py` (add `dpa_accepted_at`, `engine_mode` fields + `dpa_accepted` property)
- `backend/core/views/account.py` (add `accept_dpa`, `set_engine_mode` views; update `account_detail` response)
- `backend/core/services/tier.py` (update `is_engine_active()` to check DPA + mode)
- `backend/core/urls.py` (add new URL patterns)
- `backend/core/models/__init__.py` (no new models, but verify exports if needed)
- `frontend/src/types/account.ts` (add DPA + mode fields)
- `frontend/src/hooks/useEngineStatus.ts` (replace stub with real logic)
- `frontend/src/app/(dashboard)/settings/page.tsx` (add mode switcher section)
- `frontend/src/app/(dashboard)/dashboard/page.tsx` (add activation CTA for Mid-tier without DPA)

### References

- [Source: epics.md#Story 3.1] — Full acceptance criteria and BDD scenarios
- [Source: architecture.md#Data Model] — Account model extension patterns
- [Source: architecture.md#API Design] — REST endpoint conventions and response envelope
- [Source: architecture.md#Cross-cutting concerns] — Audit trail via write_audit_event()
- [Source: prd.md#FR3] — DPA hard gate requirement
- [Source: prd.md#FR4] — Supervised vs Autopilot mode selection
- [Source: prd.md#FR5] — Mode switching without re-signing DPA
- [Source: ux-design-specification.md#UX-DR15] — DPA as full-page formal screen
- [Source: ux-design-specification.md#UX-DR14] — Desktop-first for complex actions
- [Source: deferred-work.md] — Engine activation post-upgrade wire-up, Stripe SDK v15 notes

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- ✅ Task 1: Added `dpa_accepted_at` and `engine_mode` fields to Account model with `dpa_accepted` property. Migration 0006 created.
- ✅ Task 2: DPA acceptance endpoint (`POST /api/v1/account/dpa/accept/`) with tier validation, idempotency, select_for_update, audit event. 7 tests in test_dpa.py.
- ✅ Task 3: Engine mode endpoint (`POST /api/v1/account/engine/mode/`) with DPA gate, first-activation vs mode-switch audit events, cache invalidation, idempotency. 9 tests in test_engine_mode.py.
- ✅ Task 4: Updated `is_engine_active()` to require tier + DPA + engine_mode. Refactored account views to use shared `_build_account_response()` helper with new DPA fields. Updated tier service tests (+2 new tests for DPA/mode gating).
- ✅ Task 5: Extended Account TypeScript interface with `dpa_accepted`, `dpa_accepted_at`, `engine_mode` fields.
- ✅ Task 6: Full-page DPA acceptance screen at `/activate` with formal DPA content sections, accept button, go-back link, loading states, and redirect guards.
- ✅ Task 7: Mode selection screen at `/activate/mode` with Autopilot/Supervised cards, plain-language descriptions and consequences, confirm button, DPA guard redirect.
- ✅ Task 8: Replaced `useEngineStatus` stub with real implementation deriving mode from `useAccount()` data.
- ✅ Task 9: Created `ActivateEngineCTA` component for Mid-tier users without DPA. Added to dashboard page above NextScanCountdown.
- ✅ Task 10: Added "Recovery Mode" section to Settings page with radio selectors, mode switch via API, toast notifications. Section only shows when DPA accepted.
- ✅ Task 11: 21 frontend tests across 5 test files: DPA page (5), mode selection (5), useEngineStatus (4), ActivateEngineCTA (4), Settings mode switcher (3).

### Review Findings

- [x] [Review][Decision] Downgrade (trial expiry / subscription.deleted) does not clear `dpa_accepted_at` or `engine_mode` — resolved: add tier check to `set_engine_mode` endpoint + Settings frontend (option 2). DPA state persists for re-upgrade convenience. (AC5, AC6, data-integrity)
- [x] [Review][Decision] AC7 "non-intrusive reminder on next login encouraging activation" — resolved: dashboard `ActivateEngineCTA` (once patched to also show when DPA accepted but mode not set) serves as the reminder. No login-specific logic needed. (AC7) — dismissed
- [x] [Review][Patch] `set_engine_mode` missing tier validation — added Mid/Pro tier check inside `select_for_update` lock [account.py] — FIXED
- [x] [Review][Patch] TOCTOU race in `accept_dpa` — moved tier check inside `select_for_update` lock [account.py] — FIXED
- [x] [Review][Patch] TOCTOU race in `set_engine_mode` — moved DPA + tier checks inside `select_for_update` lock [account.py] — FIXED
- [x] [Review][Patch] `ActivateEngineCTA` hides when `dpa_accepted` is true even if `engine_mode` is null — now checks `engine_active` instead; links to `/activate/mode` when DPA already accepted [ActivateEngineCTA.tsx] — FIXED
- [x] [Review][Patch] `useEngineStatus` derives mode from `engine_mode` field only, ignoring `engine_active` — now gates on `engine_active` boolean before reporting mode [useEngineStatus.ts] — FIXED
- [x] [Review][Patch] Audit events written outside `transaction.atomic()` — moved inside the atomic block [account.py] — FIXED
- [x] [Review][Patch] Idempotent return paths inside `transaction.atomic()` — response built after lock release; idempotent path uses pass + falls through [account.py] — FIXED
- [x] [Review][Patch] Free-tier users can navigate to `/activate` — added tier guard redirect to dashboard [activate/page.tsx] — FIXED
- [x] [Review][Patch] Settings mode switcher missing `invalidateQueries` — added after `setQueryData`; also gated section on `tier !== "free"` [settings/page.tsx] — FIXED
- [x] [Review][Defer] Expired trial accounts retain Mid-tier privileges for up to 24h until daily celery beat runs — `set_engine_mode` and `is_engine_active` don't inline-check trial expiry — deferred, pre-existing architecture (daily batch)
- [x] [Review][Defer] Frontend stale cache after webhook-driven downgrade — React Query shows `engine_active: true` until next refetch; would need WebSocket/SSE push — deferred, pre-existing architecture
- [x] [Review][Defer] `STRIPE_WEBHOOK_SECRET` defaults to empty string, not a hard startup error in production — warning logs and guard added in this diff but should be a startup check — deferred, broader config concern

### Change Log

- 2026-04-14: Implemented Story 3.1 — DPA Acceptance & Engine Mode Selection Flow. All 11 tasks completed with full test coverage.

### File List

**New files:**
- `backend/core/migrations/0006_add_dpa_engine_mode_to_account.py`
- `backend/core/tests/test_api/test_dpa.py`
- `backend/core/tests/test_api/test_engine_mode.py`
- `frontend/src/app/(dashboard)/activate/page.tsx`
- `frontend/src/app/(dashboard)/activate/mode/page.tsx`
- `frontend/src/components/dashboard/ActivateEngineCTA.tsx`
- `frontend/src/__tests__/DpaAcceptancePage.test.tsx`
- `frontend/src/__tests__/ModeSelectionPage.test.tsx`
- `frontend/src/__tests__/ActivateEngineCTA.test.tsx`
- `frontend/src/__tests__/SettingsModeSwitcher.test.tsx`

**Modified files:**
- `backend/core/models/account.py` — added `dpa_accepted_at`, `engine_mode` fields + `dpa_accepted` property
- `backend/core/views/account.py` — added `accept_dpa`, `set_engine_mode` views + `_build_account_response` helper; refactored `account_detail` and `complete_profile` to use helper
- `backend/core/services/tier.py` — updated `is_engine_active()` to require DPA + mode
- `backend/core/urls.py` — added DPA and engine mode URL patterns
- `backend/core/tests/test_api/test_profile.py` — updated engine_active tests for new DPA/mode requirements
- `backend/core/tests/test_services/test_tier.py` — updated and expanded `is_engine_active` tests
- `frontend/src/types/account.ts` — added `dpa_accepted`, `dpa_accepted_at`, `engine_mode` fields
- `frontend/src/hooks/useEngineStatus.ts` — replaced stub with real logic from `useAccount()`
- `frontend/src/app/(dashboard)/dashboard/page.tsx` — added `ActivateEngineCTA` component
- `frontend/src/app/(dashboard)/settings/page.tsx` — added Recovery Mode section with radio switcher
- `frontend/src/__tests__/useEngineStatus.test.ts` — rewritten for new real implementation
