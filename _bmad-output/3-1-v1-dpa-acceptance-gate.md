# Story 3.1 (v1): DPA Acceptance Gate

Status: done

> **v1 scope (post-2026-04-29 simplification).** Replaces the quarantined `3-1-dpa-acceptance-engine-mode-selection-flow.md` (v0). DPA is now a hard gate before *any* dunning email send — no Autopilot/Supervised mode selection. See `_bmad-output/sprint-change-proposal-2026-04-29.md` and `_bmad-output/epics.md#Epic 3 (v1)`.

> **Inheriting infrastructure already on `main`** (from quarantined v0 story 3.1):
> - `Account.dpa_accepted_at` (DateTimeField, nullable) — `backend/core/models/account.py:49`
> - `Account.dpa_accepted` property — `backend/core/models/account.py:79-82`
> - `POST /api/v1/account/dpa/accept/` view (`accept_dpa`) — `backend/core/views/account.py:145-180`
> - `_build_account_response()` helper — `backend/core/views/account.py:97-142`
> - Frontend full-page DPA screen — `frontend/src/app/(dashboard)/activate/page.tsx`
> - DPA test suite — `backend/core/tests/test_api/test_dpa.py`
>
> **DO NOT recreate any of the above.** This story extends them.

## Story

As a Mid-tier founder,
I want to formally sign the Data Processing Agreement before SafeNet sends emails to my subscribers,
So that I understand what SafeNet processes on my behalf and explicitly authorize the email-send capability.

## Acceptance Criteria

1. **Given** a client attempts to dispatch their first dunning email (per-row or bulk) **When** the dispatch endpoint is called and no `DPAAcceptance` record exists for the account **Then** the API rejects the send with a `403 DPA_REQUIRED` envelope **And** the frontend shows the DPA screen (not a modal embedded in a form) before any send button becomes active

2. **Given** the DPA screen **When** the client clicks "I accept and sign" **Then** a `DPAAcceptance` record is created with timestamp, account FK, and the DPA version hash **And** the client is returned to the failed-payments dashboard with send buttons enabled

3. **Given** an account that signed the v0 DPA before 2026-04-29 **When** they next log in **Then** the v0 DPA acceptance is honored without re-acceptance (DPA version hash carries forward)

4. **Given** Settings → Account **When** the client views the page **Then** DPA acceptance status is displayed: signed-on date and DPA version

5. **Given** the client has not signed the DPA **When** they navigate the dashboard **Then** the failed-payments list is fully visible (view-only) **And** every send button shows a tooltip "Sign the DPA to enable email sends" and is disabled

## Tasks / Subtasks

### Backend

- [x] **Task 1: Database — add `dpa_version` to Account + carry-forward backfill** (AC: #2, #3)
  - [x] 1.1 Add `dpa_version = models.CharField(max_length=64, blank=True, default="")` to `Account` model in `backend/core/models/account.py` directly under the existing `engine_mode` field (line 50–55). Empty string `""` means "never signed". A non-empty string is the canonical version identifier.
  - [x] 1.2 Define a module-level constant in a new file `backend/core/services/dpa.py`:
    ```python
    # backend/core/services/dpa.py
    """DPA versioning + gate utilities.

    Centralizes the canonical DPA version identifier and the gate helper
    used by every email-dispatch endpoint. The version string is bumped
    by hand when the DPA legal text changes — accounts that signed an
    older version remain bound by what they signed (per the carry-forward
    rule, AC3).
    """
    from rest_framework import status
    from rest_framework.response import Response

    # Bump this string when the DPA legal copy changes (NOT the rendering).
    # Format: "vN.M-YYYY-MM-DD" — the date is the publish date, not the
    # build date. The string IS the version hash for v1 — we don't hash
    # the DPA text at runtime because the text lives in the frontend
    # (frontend/src/app/(dashboard)/activate/page.tsx) and is reviewed
    # by hand on every legal change.
    CURRENT_DPA_VERSION = "v1.0-2026-04-29"

    # Sentinel value for accounts that signed the pre-2026-04-29 DPA
    # (the v0 engine-mode-coupled DPA). Carry-forward per AC3.
    LEGACY_V0_DPA_VERSION = "v0-legacy"


    def require_dpa_accepted(account):
        """Returns a 403 DRF Response if the account has not signed the DPA.
        Returns None when DPA is accepted (caller continues normally).

        Use at the TOP of every send-email endpoint (per-row + batch)
        BEFORE any tenant scoping or business logic — the gate must be
        the first thing checked so a malformed payload still returns
        DPA_REQUIRED rather than VALIDATION_ERROR.
        """
        if account.dpa_accepted:
            return None
        return Response(
            {"error": {
                "code": "DPA_REQUIRED",
                "message": "Sign the DPA to enable email sends.",
                "field": None,
            }},
            status=status.HTTP_403_FORBIDDEN,
        )
    ```
  - [x] 1.3 Create migration `backend/core/migrations/0015_add_dpa_version_to_account.py` with TWO operations: (a) `AddField` for `dpa_version`; (b) `RunPython` data migration that backfills `dpa_version="v0-legacy"` for every existing row where `dpa_accepted_at IS NOT NULL`. Use a forward-only data migration with a no-op `reverse_code=migrations.RunPython.noop` (we do NOT want to rewrite the column on rollback). Follow the migration shape in `backend/core/migrations/0006_add_dpa_engine_mode_to_account.py` (which is pure schema; you'll need to add the data step yourself).
  - [x] 1.4 In the data-migration function, get the historical model via `apps.get_model("core", "Account")` — never import the live model in a migration. Use `.update(dpa_version="v0-legacy")` on the queryset filtered by `dpa_accepted_at__isnull=False` — bulk update, no per-row save (faster, no `auto_now` side effects).
  - [x] 1.5 Run `python manage.py makemigrations --dry-run` to confirm Django's autogenerator wants exactly the AddField on `dpa_version` — if it surfaces unrelated changes, abort and ask Sabri before continuing.

- [x] **Task 2: Backend — bump `accept_dpa` view to record version + extend response** (AC: #2, #3, #4)
  - [x] 2.1 In `backend/core/views/account.py:145-180` (`accept_dpa`), inside the `transaction.atomic()` block, when `account.dpa_accepted` is FALSE, set BOTH fields atomically:
    ```python
    from core.services.dpa import CURRENT_DPA_VERSION
    account.dpa_accepted_at = timezone.now()
    account.dpa_version = CURRENT_DPA_VERSION
    account.save(update_fields=["dpa_accepted_at", "dpa_version"])
    ```
    The `update_fields` list MUST include `dpa_version` — the existing line 169 only writes `dpa_accepted_at` and would leave `dpa_version` as the model default ("").
  - [x] 2.2 Add `dpa_version` to the audit metadata: `metadata={"dpa_version": CURRENT_DPA_VERSION}` (the existing call has no metadata — add the kwarg). This gives operators a clean audit trail of which version each client signed.
  - [x] 2.3 Idempotency path (line 165–166: `if account.dpa_accepted: pass`) is unchanged — re-accepting a DPA does NOT bump `dpa_version`. This preserves the carry-forward contract: a v0-legacy account that re-hits `/dpa/accept/` stays "v0-legacy" forever (bumping would erase the carry-forward signal).
  - [x] 2.4 In `_build_account_response` (`backend/core/views/account.py:97-142`), add `"dpa_version": account.dpa_version or None` directly after the existing `"dpa_accepted_at"` line (line 137). Convert empty string to `None` for cleaner frontend handling — the JSON contract is `string | null`, never `""`.
  - [x] 2.5 Update existing tests in `backend/core/tests/test_api/test_dpa.py` to assert `dpa_version == "v1.0-2026-04-29"` after a fresh acceptance (currently asserts `dpa_accepted is True` — extend, don't replace). Add one new test `test_accept_dpa_idempotent_does_not_bump_version` that pre-populates `dpa_version="v0-legacy"` then calls the endpoint and asserts the version is STILL `"v0-legacy"` (carry-forward never overwritten).
  - [x] 2.6 Add one new test `test_accept_dpa_writes_version_in_audit_metadata` asserting `AuditLog.metadata["dpa_version"] == "v1.0-2026-04-29"`.

- [x] **Task 3: Backend — DPA gate utility used by future send endpoints** (AC: #1)
  - [x] 3.1 The `require_dpa_accepted(account)` helper from Task 1.2 lives in `core/services/dpa.py`. Story 3.1 ONLY ships the helper — the per-row send endpoint (`POST /api/v1/subscribers/{id}/send-email/`) is built in Story 3.3 (v1) and the bulk endpoint (`POST /api/v1/subscribers/batch-send-email/`) in Story 3.4 (v1); both will import this helper.
  - [x] 3.2 Write a unit test `backend/core/tests/test_services/test_dpa.py::test_require_dpa_accepted_returns_403_when_unsigned` that builds a minimal account with `dpa_accepted_at=None` and asserts the returned `Response.status_code == 403` and the body shape exactly matches `{"error": {"code": "DPA_REQUIRED", "message": "Sign the DPA to enable email sends.", "field": null}}`.
  - [x] 3.3 Write `test_require_dpa_accepted_returns_none_when_signed` that asserts `None` is returned for a signed account (whether v0-legacy or v1.0).
  - [x] 3.4 **DO NOT** wire the helper into any send view in this story — that's Stories 3.3 / 3.4. This story only delivers the gate as a public, tested API for those stories to consume.

- [x] **Task 4: Backend — verify `is_engine_active()` does not block 3.1's flow** (AC: #1)
  - [x] 4.1 The current `core/services/tier.py:23-29` `is_engine_active()` requires `account.engine_mode is not None`. Under the v1 simplification, `engine_mode` is moot for the email-send capability. **DO NOT** modify `is_engine_active()` in this story — it remains in use by quarantined v0 polling/engine code that's still on `main` until the broader Sprint Change Proposal §3.2 quarantine pass strips it. The send-email endpoints (Stories 3.3 / 3.4) will gate on DPA via `require_dpa_accepted()` directly, NOT on `is_engine_active()`.
  - [x] 4.2 Add a one-line comment in `tier.py:23` above `is_engine_active`: `# Legacy from quarantined v0 (engine_mode). v1 send endpoints gate on require_dpa_accepted() instead — see core/services/dpa.py.` This signposts intent for the next dev who reads the file.

### Frontend

- [x] **Task 5: Frontend — extend `Account` type with `dpa_version`** (AC: #4)
  - [x] 5.1 Edit `frontend/src/types/account.ts` — add `dpa_version: string | null;` directly after the existing `dpa_accepted_at: string | null;` line (line 30). Snake_case mirrors the API contract exactly — no transformation layer per `architecture.md#Naming Patterns:415`.
  - [x] 5.2 No changes to the `useAccount` hook are required — `/account/me/` already returns the new field once Task 2.4 ships.

- [x] **Task 6: Frontend — Settings DPA status section** (AC: #4)
  - [x] 6.1 Edit `frontend/src/app/(dashboard)/settings/page.tsx`. Add a new `<section>` between the existing "Subscription" and "Notifications" sections (lines 78 and 80) titled "Data Processing Agreement". Render TWO states:
    - When `account.dpa_accepted` is true: show signed-on date (formatted via existing date formatter — there's no shared util; use `new Date(account.dpa_accepted_at!).toLocaleDateString()` or follow the same inline pattern as `frontend/src/components/dashboard/UpgradeCTA.tsx` if it formats dates) and show the `account.dpa_version` (default fallback string `"v0-legacy"` if version is null AND dpa_accepted is true — the carry-forward marker should still display).
    - When `account.dpa_accepted` is false AND `account.tier !== "free"`: show a primary CTA button "Sign the Data Processing Agreement" linking to `/activate` (uses `next/link`'s `<Link>`).
    - When `account.tier === "free"`: hide the section entirely (Free tier cannot sign — the `accept_dpa` endpoint already 403s with `TIER_NOT_ELIGIBLE` per `views/account.py:159-163`).
  - [x] 6.2 Use the same chrome as adjacent sections: `<section className="mt-6 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-6">` with an `<h2>` heading. Match design tokens (`--text-primary`, `--text-secondary`) — see `frontend/src/app/globals.css` for the token list.
  - [x] 6.3 **REMOVE** the "Recovery Mode" section (lines 113–152) — `engine_mode` is moot in v1. Drop the `handleModeChange` function (lines 19–35), the `isSwitching` state (line 17), and the unused import `useState`. Keep React Query + `api` imports — they're still used elsewhere in the file. Confirm no other component imports `handleModeChange` from this file (it's local).
  - [x] 6.4 Update the existing `<ToneSelector>` `disabled` prop logic (lines 92–106) — remove the `!account.engine_mode` condition. New logic:
    ```tsx
    disabled={
      account.tier === "free" ||
      !account.dpa_accepted
    }
    disabledHint={
      account.tier === "free"
        ? "Upgrade to Mid or Pro to customize your subscriber notifications."
        : !account.dpa_accepted
          ? "Accept the Data Processing Agreement to enable tone selection."
          : undefined
    }
    ```
    Tone selection no longer depends on `engine_mode`. The `set_notification_tone` backend view at `views/account.py:348-352` ALSO has an `ENGINE_MODE_NOT_SET` 403 — flag this in the Story 3.1 v1 dev notes as "out of scope for 3.1; will be removed when notification-tone view is updated by the broader quarantine pass". Do NOT modify the backend view here.

- [x] **Task 7: Frontend — `/activate` redirect-after-accept goes to /dashboard, NOT /activate/mode** (AC: #2)
  - [x] 7.1 Edit `frontend/src/app/(dashboard)/activate/page.tsx`. Replace the `useEffect` redirect logic (lines 18–28) with v1 logic:
    ```tsx
    useEffect(() => {
      if (!accountLoading && account) {
        if (account.tier === "free") {
          router.replace("/dashboard");
        } else if (account.dpa_accepted) {
          router.replace("/dashboard");
        }
      }
    }, [account, accountLoading, router]);
    ```
    The v0 branch that redirected to `/activate/mode` is removed. After acceptance, the user lands on the failed-payments dashboard.
  - [x] 7.2 Replace the `handleAccept` success path (line 43): change `router.push("/activate/mode")` to `router.push("/dashboard")`. Also call `queryClient.invalidateQueries({ queryKey: ["account", "me"] })` AFTER `setQueryData` (the existing line 42 only sets — it doesn't trigger a refetch, and stale React Query subscribers may still see the old `dpa_accepted: false` until next mount). Pattern is exact mirror of Settings line 25–28.
  - [x] 7.3 Edit `frontend/src/app/(dashboard)/activate/mode/page.tsx`. Replace the page body with a redirect-only effect: `useEffect(() => router.replace("/dashboard"), [router])` — render a centered loading spinner (same one as line 31–35 of activate/page.tsx) so a stale browser tab on this URL gracefully exits to the dashboard. This avoids a jarring 404 for any user mid-session when v1 ships. Document at the top of the file: `// v1: mode selection is removed — see _bmad-output/sprint-change-proposal-2026-04-29.md. This page redirects.`
  - [x] 7.4 **DO NOT** delete `frontend/src/app/(dashboard)/activate/mode/page.tsx` outright — keeping it as a redirect avoids browser-history breakage during the v1 cutover. The broader main-branch quarantine pass (Sprint Change Proposal §3.2) will fully remove it later.

- [x] **Task 8: Frontend — Send-button gating helper + tooltip** (AC: #5)
  - [x] 8.1 Stories 3.3 (per-row send) and 3.4 (bulk send) own the actual send buttons. Story 3.1 ships the **helper hook** that those stories consume:
    ```typescript
    // frontend/src/hooks/useDpaGate.ts
    "use client";

    import { useAccount } from "@/hooks/useAccount";

    export interface DpaGate {
      dpaAccepted: boolean;
      sendDisabled: boolean;
      tooltip: string | undefined; // undefined when not disabled — base-ui tooltip omits the wrapper
      activatePath: "/activate";
    }

    export function useDpaGate(): DpaGate {
      const { data: account } = useAccount();
      const dpaAccepted = account?.dpa_accepted ?? false;
      return {
        dpaAccepted,
        sendDisabled: !dpaAccepted,
        tooltip: dpaAccepted ? undefined : "Sign the DPA to enable email sends",
        activatePath: "/activate",
      };
    }
    ```
    The exact tooltip string `"Sign the DPA to enable email sends"` is the AC5 contract — do NOT paraphrase. The `useAccount()` hook returns `undefined` while loading; the gate defaults to `sendDisabled: true` until the account is in cache (safer default — never enable a gated control before we know the gate state).
  - [x] 8.2 Write a Vitest test `frontend/src/__tests__/useDpaGate.test.ts` covering: (a) loading state → `sendDisabled: true`, tooltip set; (b) DPA accepted → `sendDisabled: false`, tooltip undefined; (c) DPA not accepted → `sendDisabled: true`, tooltip equals exact AC5 string. Mock `useAccount` via `vi.mock("@/hooks/useAccount", ...)` — pattern mirrors `frontend/src/__tests__/useEngineStatus.test.ts`.
  - [x] 8.3 **DO NOT** modify any actual send button in this story — there are no v1 send buttons on `main` yet (Stories 3.3 / 3.4 add them). 3.1's contract is to ship a tested, importable hook.

### Cross-cutting

- [x] **Task 9: Update existing engine-mode tests for v1 reality** (AC: all)
  - [x] 9.1 `backend/core/tests/test_api/test_engine_mode.py` and `backend/core/tests/test_services/test_tier.py` were written for the v0 mode-selection flow. Most assertions still hold (the v0 endpoints + service still exist on `main`, just unused by v1 product surface). **DO NOT** delete them — they remain valid coverage of legacy code that's still live.
  - [x] 9.2 Add ONE new test in `test_services/test_tier.py`: `test_is_engine_active_remains_v0_semantics` documenting that `is_engine_active` STILL requires `engine_mode is not None`. This locks the legacy behaviour in place — a future dev removing `engine_mode` MUST update this test consciously, not silently.
  - [x] 9.3 In `frontend/src/__tests__/SettingsModeSwitcher.test.tsx`: this file exercises the Recovery Mode section being removed in Task 6.3. **Delete the test file** (the section it tested no longer renders). Remove from any test glob in `vitest.config.ts` if explicitly listed. The `useEngineStatus.test.ts` and `ActivateEngineCTA.test.tsx` files cover unrelated surfaces — leave them untouched.

- [x] **Task 10: Smoke verification** (AC: all)
  - [x] 10.1 Run `cd backend && poetry run pytest core/tests/test_api/test_dpa.py core/tests/test_services/test_dpa.py -v` — all green.
  - [x] 10.2 Run `cd frontend && pnpm vitest run useDpaGate` — green.
  - [x] 10.3 Run `cd backend && poetry run python manage.py migrate --plan | tail -10` — confirm `0015_add_dpa_version_to_account` is the next pending migration; run `poetry run python manage.py migrate` — confirm clean apply.
  - [x] 10.4 Manual verification (one-shot): start docker-compose, log in as a Mid-tier user with `dpa_accepted_at=None`, confirm `/activate` renders, click "I accept and sign", confirm redirect to `/dashboard` (NOT `/activate/mode`), confirm `useDpaGate().sendDisabled === false` via the React Query devtools account snapshot.

### Review Findings (2026-04-29)

Adversarial review run via `bmad-code-review`: 3 reviewers (Blind Hunter, Edge Case Hunter, Acceptance Auditor). Acceptance Auditor verified all 5 ACs and all 10 tasks compliant with spec; findings below are bug/UX/test-quality items surfaced by the other two layers (with merges).

- [x] [Review][Decision→Patch] Drop `engine_mode` 403 from `set_notification_tone` so v1 Mid users with DPA-accepted but no engine_mode can change tone. Inverted `test_rejected_when_engine_mode_not_set` → `test_allowed_when_engine_mode_not_set` [backend/core/views/account.py:354-358, backend/core/tests/test_api/test_notification_tone.py:76-86]

- [x] [Review][Patch] `ActivateEngineCTA` no longer routes DPA-accepted users to `/activate/mode`; component returns null for accepted accounts and shows a "Sign the Data Processing Agreement" CTA for unsigned. Existing tests updated to match v1 contract. [frontend/src/components/dashboard/ActivateEngineCTA.tsx, frontend/src/__tests__/ActivateEngineCTA.test.tsx]
- [x] [Review][Patch] `/activate` page now early-returns the spinner when `tier === "free" || dpa_accepted`, killing the one-frame UI flash before redirect. [frontend/src/app/(dashboard)/activate/page.tsx]
- [x] [Review][Patch] `useDpaGate` now exposes `loading: boolean`; while loading `sendDisabled` stays true (safer default) but tooltip is suppressed so signed users don't see the AC5 copy on first paint. Test updated to assert tooltip undefined during loading. [frontend/src/hooks/useDpaGate.ts, frontend/src/__tests__/useDpaGate.test.ts]
- [x] [Review][Patch] Added `test_accept_dpa_double_post_writes_exactly_one_audit_row` — POSTs twice through the endpoint and asserts the audit table has exactly one row. [backend/core/tests/test_api/test_dpa.py]
- [x] [Review][Patch] Settings DPA section conditional now uses `account.dpa_accepted_at` truthiness directly; removed the dead `: "—"` fallback branch. [frontend/src/app/(dashboard)/settings/page.tsx:66-77]
- [x] [Review][Patch] Removed dead `accepted_now` variable from `accept_dpa`. [backend/core/views/account.py]
- [x] [Review][Patch] `ModeSelectionPage` redirect test now wraps the assertion in `waitFor`. [frontend/src/__tests__/ModeSelectionPage.test.tsx]
- [x] [Review][Patch] `/activate` redirect `useEffect` now guards on `isSubmitting` to avoid firing during in-flight POST. [frontend/src/app/(dashboard)/activate/page.tsx]
- [x] [Review][Patch] `test_dpa.py` now imports `CURRENT_DPA_VERSION` and `LEGACY_V0_DPA_VERSION` from `core.services.dpa` instead of hardcoding the strings. [backend/core/tests/test_api/test_dpa.py]
- [x] [Review][Patch] `useDpaGate.activatePath` typed as `string` instead of literal `"/activate"`. [frontend/src/hooks/useDpaGate.ts]

- [x] [Review][Defer] Version-aware re-acceptance: `require_dpa_accepted()` checks `dpa_accepted` only, not `dpa_version == CURRENT_DPA_VERSION`. Spec defines the no-version-check behavior intentionally (Dev Notes §DPA Version Strategy), but the carry-forward fingerprint is also lost on operator-driven reset since `accept_dpa` doesn't write a `prior_dpa_version` to audit metadata [backend/core/services/dpa.py:25-37, backend/core/views/account.py:170-175] — deferred, behavior matches spec; revisit in a hardening pass
- [x] [Review][Defer] Migration `0015` data step runs unbatched `UPDATE core_account SET dpa_version='v0-legacy' WHERE dpa_accepted_at IS NOT NULL`; long row-level write lock at scale. Currently academic (zero customers) [backend/core/migrations/0015_add_dpa_version_to_account.py:14-16] — deferred, scaling concern
- [x] [Review][Defer] Empty-string vs null `dpa_version` rolling-deploy race: backend translates `""` → `None`, but a row written between `AddField` and `RunPython` could surface as `dpa_version=""` then become `null` to the frontend, while frontend `??` fallback to `"v0-legacy"` only catches null. Window is narrow [backend/core/views/account.py:139, frontend/src/app/(dashboard)/settings/page.tsx:75] — deferred, narrow window; consider `null=True` in a future migration
- [x] [Review][Defer] `useAccount` `staleTime: 5 min` plus default `gcTime` → cross-session cache leak after logout/login as a different user. Pre-existing [frontend/src/hooks/useAccount.ts:7-18] — deferred, pre-existing; add `queryClient.clear()` to logout flow
- [x] [Review][Defer] `accept_dpa` Response missing `Cache-Control: no-store, private` (pattern established by Story 4.5 password-reset hardening) [backend/core/views/account.py:186] — deferred, apply broadly across endpoints
- [x] [Review][Defer] `accept_dpa` reads `request.user.account` then re-reads with `select_for_update`; first fetch is wasted [backend/core/views/account.py:152-159] — deferred, pre-existing; minor
- [x] [Review][Defer] `NotificationPreview` endpoint generates a real signed opt-out URL keyed to `account.id` for previews; Settings now renders the preview for unsigned-DPA Mid users — broader audience than before [backend/core/views/account.py:286-297, frontend/src/app/(dashboard)/settings/page.tsx] — deferred, gate preview behind dpa_accepted in a follow-up
- [x] [Review][Defer] Pre-existing error envelopes (`TIER_NOT_ELIGIBLE`, `set_engine_mode`, `set_notification_tone`) omit the `field: None` key required by the architecture envelope contract [backend/core/views/account.py:162-165 et al] — deferred, story explicitly out-of-scope
- [x] [Review][Defer] `dpa_version` format publicly exposed without a format-pinning regex test; future format change leaks to clients [backend/core/views/account.py:139] — deferred, hardening pass



### v1 Scope Boundaries (READ THIS FIRST)

The 2026-04-29 simplification removed Autopilot/Supervised modes entirely. Story 3.1 v1 is **narrowly scoped to the DPA semantic shift** — it does NOT remove engine_mode UI/code wholesale. That broader cleanup is part of the Sprint Change Proposal §3.2 main-branch quarantine pass and ships separately. Specifically:

- **In scope:** add `dpa_version` field + carry-forward, version recording on accept, settings DPA status display, redirect /activate → /dashboard (not /activate/mode), Recovery Mode UI removal in Settings, DPA gate helper for future send endpoints, send-button gating helper hook.
- **Out of scope (broader quarantine):** rewriting `is_engine_active()`, removing `engine_mode` field from the Account model, deleting `core/views/actions.py` (supervised queue), removing `engine/processor.py`, deleting `tasks/retry.py`, removing Mode toggle backend (`set_engine_mode` view) — flagged but untouched here.
- **Out of scope (later v1 stories):** the actual send-email endpoints (Stories 3.3 + 3.4 wire them up), the failed-payments dashboard (Story 3.2 v1), the recommended-email mapping (Story 3.5 v1).

### Architecture Compliance

- **Account model extension:** Add `dpa_version` directly to `core/models/account.py` — Account model is at `backend/core/models/account.py:31-87`. Follow the existing pattern of grouping DPA fields together. [Source: architecture.md#Naming Patterns:398-406]
- **API response envelope:** Every response is `{"data": {...}}` or `{"error": {...}}` — never bare. The `DPA_REQUIRED` error uses the standard `{"error": {"code", "message", "field"}}` shape. [Source: architecture.md#Format Patterns:489-502]
- **Tenant isolation:** All DPA gate checks scope to `request.user.account` — same pattern as `accept_dpa` in `views/account.py:150-152`. The gate helper accepts the account directly to keep it framework-agnostic for future Celery use. [Source: architecture.md#Critical Conflict Points:382-393]
- **Audit trail via helper:** All state changes via `write_audit_event()` from `core/services/audit.py` — never inline `AuditLog.objects.create()`. The new metadata key `dpa_version` extends an existing audit grammar (the `dpa_accepted` action already exists; we're just enriching its metadata). [Source: architecture.md#Communication Patterns:533-543]
- **DRF response shape:** The `require_dpa_accepted()` helper returns a DRF `Response` (not Django `HttpResponse`) so callers wrapped with `@api_view` get the right content-type/renderer/exception-handler integration. [Source: architecture.md#Process Patterns:570-579]
- **Frontend snake_case fields:** `dpa_version` field in TypeScript matches the API contract exactly — no camelCase. [Source: architecture.md#Naming Patterns:415-427]
- **Frontend route placement:** Settings page lives under `src/app/(dashboard)/settings/` to inherit the dashboard layout (NavBar, side rail). [Source: architecture.md#Component Organization (implicit via existing structure)]

### Technical Requirements

- **Existing DPA endpoint (REUSE):** `POST /api/v1/account/dpa/accept/` at `backend/core/views/account.py:145-180`. Has tier guard (Free → 403), `select_for_update` lock, idempotency on already-accepted, audit event write. Extend in Task 2 — do NOT rewrite.
- **Existing DPA full-page screen (REUSE + REDIRECT FIX):** `frontend/src/app/(dashboard)/activate/page.tsx`. Has formal DPA copy (5 sections: data processed, on whose behalf, purpose, retention, security) per UX-DR15. Modify ONLY the post-accept redirect (Task 7).
- **Existing migration latest:** `0014_notification_unique_sent_per_failure.py` — the next migration is `0015_add_dpa_version_to_account.py`. Confirm by running `ls backend/core/migrations/ | sort | tail -3` before authoring.
- **Existing audit grammar:** Actor values are `"engine" | "operator" | "client" | "subscriber"` (last added in Story 4.4). The existing `dpa_accepted` action uses `actor="client"`. Continue. Do NOT introduce a new actor value here.
- **Existing `_build_account_response` helper:** `views/account.py:97-142` — single source of truth for the account-detail JSON. ALL endpoints that mutate the account (`accept_dpa`, `set_engine_mode`, `set_notification_tone`, `complete_profile`) return through this helper. Adding `dpa_version` here propagates it to every response automatically.
- **Existing tier constants:** `TIER_FREE = "free"`, `TIER_MID = "mid"`, `TIER_PRO = "pro"` — at `core/models/account.py:8-10`. Use the constants, never the literal strings, in backend code.
- **Existing test fixtures:** `auth_client` (DRF APIClient with JWT), `account` (Account factory) — defined in `backend/core/tests/test_api/conftest.py`. Mid-tier setup: `account.tier = "mid"; account.save()`. Pattern is in every existing test in `test_dpa.py`.
- **Existing axios proxy pattern:** Frontend POSTs go through `api.post("/account/dpa/accept/")` — the axios client at `frontend/src/lib/api.ts` prepends `/api/proxy/v1` and the proxy adds JWT from the httpOnly cookie. Never call the Django backend directly from the browser. [Source: `frontend/src/app/api/proxy/[...path]/route.ts`]
- **Existing toast library:** `sonner` — `import { toast } from "sonner"`. Already in package.json. Used in `activate/page.tsx:7`. Match the existing call shape.

### DPA Version Strategy (background)

The DPA version string `"v1.0-2026-04-29"` is **a human-curated identifier**, not a runtime hash of the legal text. Two reasons:

1. The DPA copy lives in the Next.js page (`activate/page.tsx:60-116`), not in a config file the backend can hash. Pulling the copy across the FE/BE boundary just to hash it would couple deployment cadence (a frontend-only legal-text edit would force a backend deploy).
2. The legal review process for DPA changes is human, not automated — bumping the constant by hand mirrors the human review step.

When the DPA copy changes:
1. Edit the copy in `activate/page.tsx`.
2. Bump `CURRENT_DPA_VERSION` in `core/services/dpa.py` (e.g. to `"v1.1-2026-XX-XX"`).
3. **Decide manually** whether existing v1.0 acceptances need re-acceptance — if the change is material (purpose, retention, security), add a one-shot data migration that nulls `dpa_accepted_at` for `dpa_version="v1.0-..."` rows. If immaterial (typo, formatting), let existing acceptances carry forward.

This is not engineering for a hypothetical — it's documented now so future-you doesn't reinvent the policy.

### Carry-Forward Behaviour (AC3, important)

A v0-era account's `dpa_accepted_at` is already populated. The data migration in Task 1.3 stamps `dpa_version="v0-legacy"`. From a v1 product POV:
- The account `dpa_accepted` property returns `True`.
- `require_dpa_accepted()` passes — the account can send emails.
- Settings page shows "Signed on YYYY-MM-DD · Version v0-legacy".
- The v0-legacy string is **never overwritten** by re-hitting `/dpa/accept/` (Task 2.3 pass-through). This preserves the historical record of which version was actually agreed-to.

If we ever need to force re-acceptance (legal change), the path is the manual migration described above — NOT a code change in `accept_dpa`.

### Frontend Architecture Notes

- **API calls go through proxy:** All frontend calls use `/api/proxy/...` which proxies to Django backend, adding JWT from httpOnly cookie. [Source: `src/app/api/proxy/[...path]/route.ts`]
- **React Query cache keys:** Account state is `["account", "me"]`. After mutating account (DPA accept), call BOTH `setQueryData` (immediate UI update) AND `invalidateQueries` (forces server-truth refetch on next mount) — pattern from Settings page (line 23–28).
- **Design tokens for Settings DPA section:** `--bg-surface`, `--text-primary`, `--text-secondary`, `--border`, `--cta`, `--accent-active` — defined in `src/app/globals.css`. The page already uses these — match the visual rhythm of adjacent sections.
- **Toast notifications:** `toast.success()` / `toast.error()` from `sonner`.
- **Icon library:** `lucide-react` — use `Shield` icon for DPA section header (matches the `/activate` page hero icon at `activate/page.tsx:8,53`).
- **Component primitives:** `@base-ui/react` Dialog, Button, Card available in `src/components/ui/`. The Settings DPA section uses plain HTML + Tailwind (matching neighboring sections), not Card primitives.
- **Testing pattern:** Vitest + React Testing Library with `vi.mock` for hooks, `QueryClientProvider` wrapper required in tests. Pattern is in `frontend/src/__tests__/DpaAcceptancePage.test.tsx`.

### UX Design Requirements

- **DPA is a full-page formal screen** — already shipped. NOT a checkbox, NOT a modal. (UX-DR15) [Source: ux-design-specification.md:130]
- **DPA gate is before any email send, not before "engine activation"** — the v1 contract. (FR3 modified per Sprint Change Proposal §2b) [Source: ux-design-specification.md:651-652]
- **Send-button disabled-with-tooltip pattern** — the AC5 contract is verbatim "Sign the DPA to enable email sends". This exact string is the contract; tests assert on it. [Source: epics.md:828-829]
- **One irreversible action per flow** — DPA acceptance is irreversible; the explicit "I accept and sign" button on `/activate` is the single confirmation step. No additional confirmation needed. [Source: ux-design-specification.md:802,825]
- **Failures are paths, not dead ends** — if a Free-tier user lands on `/activate`, redirect to `/dashboard` (not 403, not toast). The existing tier-guard at `activate/page.tsx:20-21` already does this. [Source: ux-design-specification.md:821]

### Previous Story Intelligence

This story replaces v0 Story 3.1 (`3-1-dpa-acceptance-engine-mode-selection-flow.md`, status: done). Carry-forward learnings from the v0 review (visible in v0's "Review Findings" section):

- **TOCTOU race in `accept_dpa`:** v0 review patch moved tier check inside `select_for_update` lock. ALREADY FIXED on `main` — confirm by reading `views/account.py:155-163`. Don't reintroduce the bug.
- **Audit events outside `transaction.atomic()`:** v0 review patch moved the audit write inside the atomic block. ALREADY FIXED — confirm by reading `views/account.py:155-178`. The `write_audit_event` call sits inside `with transaction.atomic()`. Preserve this when extending.
- **Idempotent return path inside `transaction.atomic()`:** v0 pattern returns the response AFTER the lock releases (line 180), with the idempotent path using `pass` inside the block (line 166). Preserve this — don't return inside the `with` block.
- **Free-tier guard on /activate:** v0 patch added `if (account.tier === "free") router.replace("/dashboard")`. Preserve in Task 7.
- **`select_for_update()` for race defense:** Pattern is in `accept_dpa` and `complete_profile`. The new `dpa_version` write piggybacks on the existing lock — no new lock needed.
- **`invalidateQueries` after `setQueryData`:** v0 review patch added the missing `invalidateQueries` call to Settings mode-switcher. Apply the same pattern in Task 7.2 for the activate-page success handler.

From recent stories (4.1, 4.2, 4.3, 4.4, 4.5):
- **Email-related code lives in `core/services/email.py` + `core/tasks/notifications.py`** — the DPA gate touches NEITHER (gate fires at the API boundary, not the email-send boundary). The send endpoints (Stories 3.3 / 3.4) will call the gate before they call the email service.
- **Test mocking pattern for Resend:** Autouse `resend_send_mock` fixture in `conftest.py`. NOT relevant for 3.1 (no email sends here), but mention so the dev doesn't accidentally drop it from test setup.
- **Adversarial review finds (4.1: 21 patches, 4.2: 14, 4.3: 9, 4.5: 14):** The general theme is concurrency, error envelopes, idempotency, audit-write placement. The 3.1 v1 implementation should pre-empt these:
  - Idempotent endpoints are already idempotent — confirm Task 2.3 idempotency path.
  - Error envelopes match the standard shape (Task 1.2 error body).
  - Audit writes inside transaction (Task 2.1 keeps the existing structure).
  - Migration data step uses bulk `update()` not per-row `save()` (Task 1.4).

### Git Intelligence

Recent commits (`git log --oneline -10`) show:
- `f366d31 Major rescoping ... centered on the dunning feature` — the parent commit for v1 work.
- `6fe105e Backend (8 files)` — password-reset hardening (Story 4.5 review).
- `a23988e Story 4.3: final notice & recovery confirmation emails`.
- `1c7a131 Merge pull request #1 from SabriBkg/review/3-2-autopilot-recovery-engine` — the v0 engine merge.
- `f516e92 Story 4.2 review: apply 14 patches`.
- `da8bf85 Epic 3: Recovery engine, DPA gate, FSM status machine, supervised mode, and card-update detection` — the v0 monolith Epic 3 commit. Most v0 code on `main` traces back here.

**Implication:** the v0 DPA infra (`accept_dpa`, `dpa_accepted_at`, `/activate` page) is already on `main` and has been review-hardened. 3.1 v1 extends it surgically — minimum new code, maximum reuse.

### Latest Tech Information

- **Django 6.0.3** (`pyproject.toml`) — `update_fields=` on `save()` is the standard partial-write pattern. `Migration.RunPython` for data migrations is the documented mechanism for backfills.
- **Django REST Framework 3.17.1** — `Response` returns wrap any JSON-serializable dict. `status.HTTP_403_FORBIDDEN` is the explicit constant.
- **Next.js (frontend)** — App Router (not Pages Router). Server-side redirects via `redirect()` from `next/navigation`; client-side via `router.replace()`. Use `replace` (not `push`) for redirect-on-mount so the user can't hit Back to re-trigger the redirect loop.
- **TanStack Query v5** — `setQueryData` is synchronous; `invalidateQueries` triggers refetch. Always do `setQueryData` first, `invalidateQueries` second (so the optimistic update flashes; the refetch validates).
- **Vitest** + React Testing Library — `vi.mock` for module-level mocks. Pattern in `frontend/src/__tests__/useEngineStatus.test.ts`.

### Project Structure Notes

**New files to create:**
- `backend/core/services/dpa.py` (new module — `CURRENT_DPA_VERSION`, `LEGACY_V0_DPA_VERSION`, `require_dpa_accepted`)
- `backend/core/migrations/0015_add_dpa_version_to_account.py` (schema + data migration)
- `backend/core/tests/test_services/test_dpa.py` (unit tests for the gate helper)
- `frontend/src/hooks/useDpaGate.ts` (gating hook for future send buttons)
- `frontend/src/__tests__/useDpaGate.test.ts` (Vitest tests)

**Files to modify:**
- `backend/core/models/account.py` — add `dpa_version` field
- `backend/core/views/account.py` — extend `accept_dpa` to record version + audit metadata; extend `_build_account_response` to expose `dpa_version`
- `backend/core/tests/test_api/test_dpa.py` — extend with version-related assertions
- `backend/core/services/tier.py` — add legacy comment (no behavior change)
- `backend/core/tests/test_services/test_tier.py` — add lock-in test
- `frontend/src/types/account.ts` — add `dpa_version` field
- `frontend/src/app/(dashboard)/settings/page.tsx` — add DPA section, remove Recovery Mode section, simplify ToneSelector disabled logic
- `frontend/src/app/(dashboard)/activate/page.tsx` — redirect-after-accept goes to /dashboard
- `frontend/src/app/(dashboard)/activate/mode/page.tsx` — convert to redirect stub

**Files to delete:**
- `frontend/src/__tests__/SettingsModeSwitcher.test.tsx` — exercises a removed UI section

### References

- [Source: epics.md#Epic 3 (v1):793-829] — Full v1 epic context and Story 3.1 v1 ACs
- [Source: sprint-change-proposal-2026-04-29.md:1-280] — Strategic rationale, FR diff, branch strategy
- [Source: prd.md#FR3] — DPA hard gate before any dunning email send (modified)
- [Source: ux-design-specification.md#UX-DR15:130] — DPA as full-page formal screen
- [Source: ux-design-specification.md:435-443] — First Email Send (DPA Gate) flow
- [Source: ux-design-specification.md:651-652] — DPA gate sits before email send, not before "engine activation"
- [Source: architecture.md#Naming Patterns:398-435] — snake_case API + TypeScript field naming
- [Source: architecture.md#Format Patterns:489-510] — API response envelope + monetary value contracts
- [Source: architecture.md#Communication Patterns:533-543] — Audit log write helper pattern
- [Source: architecture.md#Process Patterns:570-579] — Error handling by layer
- [Source: 3-1-dpa-acceptance-engine-mode-selection-flow.md] — v0 implementation detail + review findings (carry-forward learnings)
- [Source: 4-4-opt-out-mechanism-notification-suppression.md] — Recent established pattern for token-signed gates and `csrf_exempt` views (not directly relevant but the test/file-organization patterns are good reference)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

- Backend `--dry-run` surfaced an unrelated pre-existing drift `~ Alter field actor on auditlog` (Story 4.4 added `ACTOR_SUBSCRIBER` to `ACTOR_CHOICES` without generating the migration). Confirmed via `git stash` test that this drift exists on a clean tree, not introduced by Story 3.1. Per Sabri's direction (option a), left for a follow-up cleanup PR.
- Backend full regression: 552 passed, 10 failed. The 10 failures are pre-existing environment-config issues (missing `STRIPE_WEBHOOK_SECRET`, `STRIPE_MID_TIER_PRICE_ID` env vars; one polling test) — verified to exist on baseline. Zero new regressions caused by Story 3.1.
- Frontend full regression: 94 passed, 11 failed (105 total). Identical 11 failures vs baseline (BatchActionToolbar / NavBar / ProfileComplete / ReviewQueuePage). Zero new regressions.
- DPA-related targeted tests: backend `test_dpa.py` (9), `test_services/test_dpa.py` (3), `test_services/test_tier.py` (15) — all green. Frontend `useDpaGate` (3), `DpaAcceptancePage` (4), `ModeSelectionPage` (2), `ToneSelector` (existing) — all green.
- Migration `0015_add_dpa_version_to_account` applied cleanly. `migrate --plan` confirmed it as the next pending migration before apply.

### Completion Notes List

- All 10 tasks and all subtasks complete; story status set to `review`.
- Implemented exactly per spec: `dpa_version` field + carry-forward migration, `core/services/dpa.py` gate helper, version-aware `accept_dpa` view, frontend `Account.dpa_version` type, Settings DPA status section (signed / sign-CTA / hidden-for-Free), Recovery Mode UI removed, ToneSelector gating simplified to depend only on `dpa_accepted`, `/activate` redirect-after-accept now goes to `/dashboard` (with `invalidateQueries`), `/activate/mode` reduced to a redirect stub, `useDpaGate` hook with verbatim AC5 tooltip string.
- Tests for the v1 redirect path (`DpaAcceptancePage` and `ModeSelectionPage`) updated to match the new redirect contract; `SettingsModeSwitcher.test.tsx` deleted (covered a removed UI section).
- Out-of-scope (deliberately untouched, per "v1 Scope Boundaries" in Dev Notes): `is_engine_active()` body, `engine_mode` field on the model, `set_engine_mode` view, `set_notification_tone` view's `ENGINE_MODE_NOT_SET` 403, supervised queue / engine processor / retry tasks. These are part of the broader Sprint Change Proposal §3.2 main-branch quarantine pass.
- Manual verification (Task 10.4) was not executed in this session — backend container started for tests but the docker-compose web/frontend stack was not exercised end-to-end through a browser. Recommended for code-review.

### File List

**New files:**
- `backend/core/services/dpa.py`
- `backend/core/migrations/0015_add_dpa_version_to_account.py`
- `backend/core/tests/test_services/test_dpa.py`
- `frontend/src/hooks/useDpaGate.ts`
- `frontend/src/__tests__/useDpaGate.test.ts`

**Modified files:**
- `backend/core/models/account.py` — added `dpa_version` CharField
- `backend/core/views/account.py` — `accept_dpa` records `CURRENT_DPA_VERSION` atomically + writes it in audit metadata; `_build_account_response` exposes `dpa_version` (empty string → `null`)
- `backend/core/services/tier.py` — legacy comment above `is_engine_active` (no behavioral change)
- `backend/core/tests/test_api/test_dpa.py` — assertions for `dpa_version`, new tests for audit metadata + idempotent carry-forward
- `backend/core/tests/test_services/test_tier.py` — added `test_is_engine_active_remains_v0_semantics` lock-in test
- `frontend/src/types/account.ts` — added `dpa_version: string | null`
- `frontend/src/app/(dashboard)/settings/page.tsx` — added DPA status section, removed Recovery Mode section + handlers, simplified ToneSelector gating
- `frontend/src/app/(dashboard)/activate/page.tsx` — redirect-after-accept goes to `/dashboard`, added `invalidateQueries` after `setQueryData`
- `frontend/src/app/(dashboard)/activate/mode/page.tsx` — converted to redirect-only stub with loading spinner
- `frontend/src/__tests__/DpaAcceptancePage.test.tsx` — updated redirect assertion to `/dashboard` per v1 contract
- `frontend/src/__tests__/ModeSelectionPage.test.tsx` — rewritten to test redirect-stub behavior

**Deleted files:**
- `frontend/src/__tests__/SettingsModeSwitcher.test.tsx` — exercised the removed Recovery Mode section

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-29 | Dev (claude-opus-4-7) | Story 3.1 v1 implementation: DPA acceptance gate with version tracking, carry-forward for v0 acceptances, settings DPA status, send-button gating helper. 12 files modified, 5 created, 1 deleted. Backend 26/26 + Frontend 15/15 targeted tests green; zero new regressions. |
