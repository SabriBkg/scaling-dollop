# Story 2.4: Failure Landscape Dashboard & KPI Cards

Status: done

## Story

As a connected founder,
I want my dashboard to show a populated failure landscape with estimated recoverable revenue, decline-code breakdown, and the Story Arc 3-column layout,
so that I understand my payment health at a glance and the upgrade value is always visible.

## Acceptance Criteria

1. **Given** a client with completed retroactive scan data **When** they load the dashboard **Then** the `StoryArcPanel` renders 3 columns (Detected → In Progress → Recovered) via CSS Grid with 1px hairline dividers (UX-DR3) **And** Column 1 shows total failures detected + subscriber count with neutral colour **And** Column 2 shows estimated recoverable revenue (bold, 52px) + recovery rate as secondary KPI, in blue (FR9, UX-DR2) **And** Column 3 shows recovered this month in green (56px Inter 700) + retry count + net benefit (UX-DR2)

2. **Given** the dashboard API endpoint `/api/v1/dashboard/summary/` **When** called **Then** it returns aggregated KPIs in `{data: {...}}` envelope with all monetary values as integer cents **And** the response is cached with a 5-minute TTL in Redis, invalidated on any new engine action for that account **And** it responds within 3 seconds for accounts with up to 500 subscribers (NFR-P1)

3. **Given** a free-tier client viewing the dashboard **When** the estimated recoverable revenue figure is visible **Then** a single upgrade CTA is anchored directly below it: "Activate recovery engine — €29/month" (FR39, FR9) **And** no other primary CTA competes for attention on the same screen

4. **Given** the failure breakdown section (FR8, FR30) **When** rendered below the StoryArcPanel **Then** each decline code category is shown with a plain-language label via `DeclineCodeExplainer` (e.g., "Card expired", "Insufficient funds") — no raw Stripe codes visible (UX-DR7) **And** each category shows subscriber count, total amount at risk, and a colour-coded indicator

5. **Given** the dashboard is loading **When** TanStack Query is fetching data **Then** skeleton screens mirror the exact shape of loaded content: 3 StoryArc column skeletons + 6 SubscriberCard skeletons (UX-DR11) **And** the dashboard never shows an empty state after a completed scan — data is always present (FR29, UX-DR18)

6. **Given** all interactive elements on the dashboard **When** navigated via keyboard **Then** all have visible focus rings using `--accent-active` colour **And** all KPI numbers have `aria-label` with currency and context (e.g., "€640 estimated recoverable revenue") **And** scan animations and transitions respect `prefers-reduced-motion` (UX-DR13)

## Tasks / Subtasks

- [x] Task 1: Backend — Dashboard Summary API Endpoint (AC: #2)
  - [x] 1.1 Create `core/views/dashboard.py` with `DashboardSummaryView` (GET `/api/v1/dashboard/summary/`)
  - [x] 1.2 Create `core/serializers/dashboard.py` with `DashboardSummarySerializer`
  - [x] 1.3 Implement aggregation query: total failures, subscriber count, estimated recoverable revenue (sum of amounts where decline code ∉ {fraudulent, card_expired, card_lost_or_stolen, no_account}), recovered this month (sum + count), recovery rate, by-decline-code breakdown
  - [x] 1.4 Add Redis cache with 5-min TTL using `django-redis` cache framework — cache key scoped to `account_id`
  - [x] 1.5 Wire endpoint in `core/urls.py` under `/api/v1/dashboard/`
  - [x] 1.6 Write tests in `tests/test_api/test_dashboard.py` — verify response envelope, aggregation accuracy, cache behavior, tenant isolation

- [x] Task 2: Backend — Decline Code Breakdown Endpoint (AC: #4)
  - [x] 2.1 Add decline-code aggregation to `DashboardSummaryView` response (or as sub-resource `/api/v1/dashboard/decline-breakdown/`)
  - [x] 2.2 Each entry: `decline_code`, `human_label`, `subscriber_count`, `total_amount_cents`, `recovery_action`
  - [x] 2.3 Map decline codes to human labels using existing `DECLINE_RULES` in `core/engine/rules.py` — add a `human_label` mapping dict
  - [x] 2.4 Test: verify all codes return human-readable labels, no raw Stripe codes leak

- [x] Task 3: Frontend — `useDashboardSummary` Hook (AC: #2, #5)
  - [x] 3.1 Create `src/hooks/useDashboardSummary.ts` — TanStack Query hook calling `GET /api/v1/dashboard/summary/`
  - [x] 3.2 Set `staleTime: 5 * 60 * 1000` (5 min), `refetchInterval: 5 * 60 * 1000`
  - [x] 3.3 Define TypeScript interface `DashboardSummary` in `src/types/dashboard.ts` — all monetary fields as `number` (integer cents), snake_case fields matching API

- [x] Task 4: Frontend — `StoryArcPanel` Component (AC: #1, #5, #6)
  - [x] 4.1 Create `src/components/dashboard/StoryArcPanel.tsx`
  - [x] 4.2 CSS Grid layout: 3 equal columns with 1px `--sn-border` hairline dividers
  - [x] 4.3 Column 1 (Detected): neutral `--text-primary` — total failures count + subscriber count
  - [x] 4.4 Column 2 (In Progress): `--accent-active` blue — estimated recoverable revenue at 52px Inter 700 bold + recovery rate % secondary
  - [x] 4.5 Column 3 (Recovered): `--accent-recovery` green — recovered this month at 56px Inter 700 + retry count + net benefit
  - [x] 4.6 Each column: step indicator (numbered badge + label), hero metric, supporting KPIs
  - [x] 4.7 All monetary values: use `formatCurrency` from `src/lib/formatters.ts` (convert cents → display)
  - [x] 4.8 `font-variant-numeric: tabular-nums` on all numbers
  - [x] 4.9 Each column: `role="region"` + descriptive `aria-label`
  - [x] 4.10 Skeleton state: `StoryArcPanelSkeleton` — 3 column placeholders matching loaded shape
  - [x] 4.11 Responsive: 3 columns at `lg:` (≥1024px), stacked single column below

- [x] Task 5: Frontend — `KPICard` Component (AC: #1, #6)
  - [x] 5.1 Create `src/components/dashboard/KPICard.tsx` — reusable card: eyebrow label, hero number, supporting text
  - [x] 5.2 Props: `label`, `value`, `formattedValue`, `supportingText`, `color` (neutral/blue/green), `ariaLabel`
  - [x] 5.3 `aria-label` on hero number with currency and context
  - [x] 5.4 Focus ring using `--accent-active`

- [x] Task 6: Frontend — `DeclineCodeExplainer` Component (AC: #4, #6)
  - [x] 6.1 Create `src/components/dashboard/DeclineCodeExplainer.tsx`
  - [x] 6.2 Map of decline codes → human labels (source: backend provides `human_label` in API response)
  - [x] 6.3 Display: human label + subscriber count + total amount + colour indicator (green = recoverable, amber = notify-only, red = fraud)
  - [x] 6.4 Never show raw Stripe codes in UI

- [x] Task 7: Frontend — Decline Breakdown Section (AC: #4)
  - [x] 7.1 Create `src/components/dashboard/DeclineBreakdown.tsx` — renders below StoryArcPanel
  - [x] 7.2 List of `DeclineCodeExplainer` rows, sorted by subscriber count descending
  - [x] 7.3 Skeleton state matching loaded shape

- [x] Task 8: Frontend — Upgrade CTA (AC: #3)
  - [x] 8.1 Create `src/components/dashboard/UpgradeCTA.tsx`
  - [x] 8.2 Conditionally rendered when account tier = "free" (use `useAccount` hook, check `tier` field)
  - [x] 8.3 Text: "Activate recovery engine — €29/month"
  - [x] 8.4 Anchored directly below estimated recoverable revenue in StoryArcPanel Column 2
  - [x] 8.5 Uses `--cta` colour token, single primary CTA — no competing CTAs on screen

- [x] Task 9: Frontend — Dashboard Page Integration (AC: #1, #3, #4, #5, #6)
  - [x] 9.1 Update `src/app/(dashboard)/page.tsx` — compose: StoryArcPanel + DeclineBreakdown
  - [x] 9.2 Wire `useDashboardSummary` hook, pass data to components
  - [x] 9.3 Loading state: show skeletons via TanStack Query `isLoading`
  - [x] 9.4 Never show empty state after completed scan
  - [x] 9.5 Keyboard navigation: all interactive elements have visible focus rings

- [x] Task 10: Frontend Tests (AC: all)
  - [x] 10.1 Test `StoryArcPanel` renders 3 columns with correct data
  - [x] 10.2 Test `DeclineBreakdown` renders human-readable labels, no raw codes
  - [x] 10.3 Test `UpgradeCTA` renders only for free-tier accounts
  - [x] 10.4 Test skeleton states render during loading
  - [x] 10.5 Test accessibility: `aria-label` on KPIs, `role="region"` on columns

## Dev Notes

### Architecture Compliance

- **Backend view location:** `core/views/dashboard.py` — already specified in architecture [Source: architecture.md#Views Organization]
- **Backend serializer:** `core/serializers/dashboard.py` — new file following existing pattern
- **Frontend component location:** `src/components/dashboard/` — architecture specifies this folder for dashboard components [Source: architecture.md#Component Organization]
- **Hook location:** `src/hooks/useDashboardSummary.ts` — one hook per file [Source: architecture.md#TanStack Query Hook Pattern]
- **Types location:** `src/types/dashboard.ts` — shared types in `src/types/` [Source: architecture.md#Component File Organization]
- **API response:** Must use `{data: {...}}` envelope — never bare root objects [Source: architecture.md#API Response Envelope]
- **Monetary values:** Integer cents in API (`amount_cents: 6400`), formatted in frontend only via `formatCurrency` [Source: architecture.md#Monetary Values]
- **TypeScript fields:** snake_case matching API — no camelCase transformation [Source: architecture.md#TypeScript Type Naming]
- **Tenant isolation:** All queries must scope to `account_id` via `TenantManager` [Source: architecture.md#Tenant Isolation]

### Technical Requirements

- **Cache:** Use `django-redis` (already configured) with `cache.set(key, data, 300)` — key format: `dashboard_summary_{account_id}`
- **Cache invalidation:** Signal or helper to invalidate on engine actions — for now, TTL-based expiry is sufficient since engine actions are hourly
- **Query performance:** Aggregation on `SubscriberFailure` table scoped to account — ensure `idx_subscriber_failure_account_id` index exists (should from prior stories)
- **API versioning:** `/api/v1/` prefix — already established
- **Authentication:** JWT required — use existing DRF authentication classes
- **Pagination:** Not needed for summary endpoint (single aggregated response)

### Library & Framework Requirements

- **Backend:** Django 6.0.x, DRF 3.17.x, `django-redis` for caching — all already installed
- **Frontend:** Next.js 16.x, TanStack Query v5, Zustand, Tailwind CSS, shadcn/ui — all already installed
- **Charting:** No external charting library needed — StoryArcPanel is a custom CSS Grid layout with KPI numbers, not a chart
- **Fonts:** Inter (already configured in root layout) — hero numbers at 52px/56px weight 700
- **Icons:** `lucide-react` (already installed)

### Design Token Reference

All tokens already defined in `frontend/src/app/globals.css` from Story 1.4:

| Token | Light | Dark | Usage in this story |
|-------|-------|------|---------------------|
| `--bg-surface` | #FFFFFF | #1A1D27 | Card backgrounds |
| `--sn-border` | #E2E5EF | #2D3148 | Column dividers (1px hairline) |
| `--text-primary` | #0F1117 | #F9FAFB | Column 1 metrics (neutral) |
| `--text-secondary` | #4B5563 | #9CA3AF | Labels, supporting copy |
| `--accent-active` | #3B82F6 | #60A5FA | Column 2 metrics (blue), focus rings |
| `--accent-recovery` | #10B981 | #10B981 | Column 3 metrics (green) |
| `--accent-fraud` | #EF4444 | #F87171 | Fraud indicator in decline breakdown |
| `--cta` | #3B82F6 | #60A5FA | Upgrade CTA button |

### API Response Shape

```typescript
// GET /api/v1/dashboard/summary/
interface DashboardSummary {
  total_failures: number          // count of all detected failures
  total_subscribers: number       // unique subscriber count with failures
  estimated_recoverable_cents: number  // sum of amounts for recovery-eligible codes
  recovered_this_month_cents: number   // sum of recovered amounts this month
  recovered_count: number         // count of recovered subscribers this month
  recovery_rate: number           // percentage (0-100)
  net_benefit_cents: number       // recovered minus subscription cost
  decline_breakdown: DeclineBreakdownEntry[]
}

interface DeclineBreakdownEntry {
  decline_code: string            // internal code (not shown in UI)
  human_label: string             // "Card expired", "Insufficient funds", etc.
  subscriber_count: number
  total_amount_cents: number
  recovery_action: string         // "retry_notify" | "notify_only" | "fraud_flag" | "no_action"
}
```

### Decline Code → Human Label Mapping

Add to backend (e.g., `core/engine/rules.py` or new `core/engine/labels.py`):

| Decline Code | Human Label |
|---|---|
| `card_expired` | Card expired |
| `insufficient_funds` | Insufficient funds |
| `do_not_honor` | Payment declined by bank |
| `generic_decline` | Payment declined |
| `fraudulent` | Fraud flagged |
| `card_lost_or_stolen` | Card reported lost or stolen |
| `card_velocity_exceeded` | Too many payment attempts |
| `authentication_required` | Authentication required |
| `authentication_failure` | Authentication failed |
| `processing_error` | Processing error |
| `issuer_temporarily_unavailable` | Bank temporarily unavailable |
| `expired_token` | Payment method expired |
| `no_account` | Account closed |
| `_default` | Payment declined |

### Previous Story Intelligence (Story 2.3)

**Patterns established to follow:**
- Components in `src/components/common/` for shared, `src/components/dashboard/` for dashboard-specific
- Hooks use TanStack Query with `staleTime` config — see `useAccount.ts` as reference pattern
- Test files in `src/__tests__/` using vitest + @testing-library/react + happy-dom
- vitest config at `frontend/vitest.config.mts`
- shadcn components in `src/components/ui/` — add new ones via `npx shadcn@latest add [component]`

**Existing code to reuse:**
- `src/lib/api.ts` — axios instance with JWT interceptor
- `src/lib/formatters.ts` — `formatCurrency()` for cents → display conversion
- `src/lib/constants.ts` — API base URL, route constants
- `src/stores/uiStore.ts` — theme preference, UI state
- `src/hooks/useAccount.ts` — account data including `tier` field (for upgrade CTA logic)
- `src/hooks/useEngineStatus.ts` — stub hook (returns paused mode for now)
- `src/types/account.ts` — existing account types
- `src/app/(dashboard)/layout.tsx` — dashboard shell with NavBar (renders page.tsx as children)
- `frontend/vitest.config.mts` — test configuration already set up

**Deferred items from Story 2.3 to be aware of:**
- `useAccount` error state is unhandled — broader concern, don't fix here
- Mobile navigation limited — don't add mobile features here
- EngineStatusIndicator returns stub data — don't change, Story 3.1+ will implement

### File Structure

**New files:**
- `backend/core/views/dashboard.py`
- `backend/core/serializers/dashboard.py`
- `backend/tests/test_api/test_dashboard.py`
- `frontend/src/types/dashboard.ts`
- `frontend/src/hooks/useDashboardSummary.ts`
- `frontend/src/components/dashboard/StoryArcPanel.tsx`
- `frontend/src/components/dashboard/KPICard.tsx`
- `frontend/src/components/dashboard/DeclineCodeExplainer.tsx`
- `frontend/src/components/dashboard/DeclineBreakdown.tsx`
- `frontend/src/components/dashboard/UpgradeCTA.tsx`
- `frontend/src/__tests__/StoryArcPanel.test.tsx`
- `frontend/src/__tests__/DeclineBreakdown.test.tsx`
- `frontend/src/__tests__/UpgradeCTA.test.tsx`

**Modified files:**
- `backend/core/urls.py` — add dashboard endpoint route
- `backend/core/engine/rules.py` — add `DECLINE_CODE_LABELS` mapping dict
- `frontend/src/app/(dashboard)/page.tsx` — compose dashboard components

### Anti-Pattern Prevention

- **DO NOT** use `useState` for server data — use TanStack Query exclusively
- **DO NOT** use camelCase in TypeScript interfaces for API fields
- **DO NOT** store monetary values as floats — integer cents only
- **DO NOT** display raw Stripe decline codes in UI — always use human labels
- **DO NOT** create a `Model.objects.all()` query without account scoping
- **DO NOT** bypass the `{data: {...}}` response envelope
- **DO NOT** add an external charting library — this is a CSS Grid layout with KPI numbers
- **DO NOT** cache individual subscriber data — only aggregate summaries
- **DO NOT** mock database in backend tests — use real test database

### Project Structure Notes

- All paths align with monorepo structure: `backend/` for Django, `frontend/` for Next.js
- Backend follows established pattern: views → serializers → models → tests
- Frontend follows established pattern: hooks → components → types → tests
- No new dependencies needed — all libraries already installed from prior stories

### References

- [Source: architecture.md#Views Organization] — `core/views/dashboard.py` location
- [Source: architecture.md#Dashboard Summary API] — `/api/v1/dashboard/summary/` endpoint spec
- [Source: architecture.md#Component Organization] — `src/components/dashboard/` location
- [Source: architecture.md#TanStack Query Hook Pattern] — `useDashboardSummary` pattern
- [Source: architecture.md#API Response Envelope] — `{data: {...}}` format
- [Source: architecture.md#Monetary Values] — integer cents convention
- [Source: ux-design-specification.md#StoryArcPanel] — 3-column layout spec
- [Source: ux-design-specification.md#RecoveryHeroCard] — hero KPI typography
- [Source: ux-design-specification.md#DeclineCodeExplainer] — human label mapping
- [Source: ux-design-specification.md#Accessibility] — WCAG AA, aria-labels, focus rings
- [Source: ux-design-specification.md#Loading States] — skeleton screen spec
- [Source: prd.md#KPI Metrics] — metric definitions and calculations
- [Source: prd.md#Decline Code Classification] — recovery action mapping
- [Source: epics.md#Story 2.4] — acceptance criteria source

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- UpgradeCTA test initially failed due to multiple vi.mock() calls in same file — fixed by using mockReturnValue pattern with beforeEach reset

### Completion Notes List
- Task 1-2 (Backend): Created `DashboardSummaryView` at `GET /api/v1/dashboard/summary/` with aggregation queries scoped via TenantManager, 5-min Redis cache (TTL 300s, key `dashboard_summary_{account_id}`), `{data: {...}}` response envelope, DashboardSummarySerializer. Decline breakdown included inline with human-readable labels via new `core/engine/labels.py`. 13 backend tests: response envelope, aggregation accuracy, cache behavior, tenant isolation, recovery rate, monetary integers, label completeness.
- Task 3 (Frontend Hook): Created `useDashboardSummary` TanStack Query hook with 5-min staleTime and refetchInterval. TypeScript interfaces in `src/types/dashboard.ts` with snake_case fields and integer cents.
- Task 4-5 (StoryArcPanel + KPICard): CSS Grid 3-column layout with `--sn-border` dividers. Column 1 neutral, Column 2 blue (52px), Column 3 green (56px). Step badges, `font-variant-numeric: tabular-nums`, `role="region"` + `aria-label` on each column. Responsive: stacked on mobile, 3-col at lg. Skeleton state included.
- Task 6-7 (DeclineCodeExplainer + DeclineBreakdown): Colour-coded indicators (green=recoverable, amber=notify-only, red=fraud). Sorted by subscriber count descending. 6-row skeleton state. No raw Stripe codes in UI.
- Task 8 (UpgradeCTA): Conditionally rendered for free-tier accounts only. Uses `--cta` colour token. Anchored below Column 2 in StoryArcPanel.
- Task 9 (Dashboard Page): Composed all components with `useDashboardSummary`. Shows skeletons during loading, never shows empty state.
- Task 10 (Frontend Tests): 8 StoryArcPanel tests (3 columns, aria-labels, data rendering, step badges, skeleton), 7 DeclineBreakdown tests (human labels, no raw codes, sorting, amounts, skeleton), 3 UpgradeCTA tests (free/mid/loading).

### File List
- `backend/core/views/dashboard.py` (new) — Dashboard summary API view with aggregation and caching
- `backend/core/serializers/__init__.py` (new) — Serializers package init
- `backend/core/serializers/dashboard.py` (new) — DashboardSummary and DeclineBreakdownEntry serializers
- `backend/core/engine/labels.py` (new) — Decline code to human label mapping
- `backend/core/urls.py` (modified) — Added dashboard summary endpoint
- `backend/core/tests/test_api/test_dashboard.py` (new) — 13 backend tests
- `frontend/src/types/dashboard.ts` (new) — DashboardSummary and DeclineBreakdownEntry TypeScript interfaces
- `frontend/src/hooks/useDashboardSummary.ts` (new) — TanStack Query hook for dashboard API
- `frontend/src/components/dashboard/KPICard.tsx` (new) — Reusable KPI card component
- `frontend/src/components/dashboard/StoryArcPanel.tsx` (new) — 3-column story arc panel with skeleton
- `frontend/src/components/dashboard/DeclineCodeExplainer.tsx` (new) — Single decline code row
- `frontend/src/components/dashboard/DeclineBreakdown.tsx` (new) — Decline breakdown section with skeleton
- `frontend/src/components/dashboard/UpgradeCTA.tsx` (new) — Conditional upgrade CTA for free tier
- `frontend/src/app/(dashboard)/dashboard/page.tsx` (modified) — Dashboard page integration
- `frontend/src/__tests__/StoryArcPanel.test.tsx` (new) — 8 tests
- `frontend/src/__tests__/DeclineBreakdown.test.tsx` (new) — 7 tests
- `frontend/src/__tests__/UpgradeCTA.test.tsx` (new) — 3 tests

### Review Findings

- [x] [Review][Decision] `recovered_count` mislabeled as "retries" — resolved: relabel UI to "recovered" instead of "retries" → patch
- [x] [Review][Decision] `net_benefit_cents` is identical to `recovered_this_month_cents` — resolved: accepted as-is, cost tracking doesn't exist yet → dismissed
- [x] [Review][Decision] Missing cache invalidation on engine actions — resolved: accepted TTL-only as documented, engine actions are hourly → dismissed
- [x] [Review][Patch] Missing `prefers-reduced-motion` support — fixed: added global CSS rule in globals.css
- [x] [Review][Patch] KPI numbers not keyboard-focusable — fixed: added `tabIndex={0}` and `role="text"` to KPICard hero span
- [x] [Review][Patch] Skeleton hero dimensions don't match loaded content — fixed: skeleton heights now h-9/h-[52px]/h-[56px] per column
- [x] [Review][Patch] UpgradeCTA positioned outside StoryArcPanel — fixed: moved inside Column 2 via `column2Footer` prop
- [x] [Review][Patch] "retries" relabeled to "recovered" — fixed: StoryArcPanel supporting text updated
- [x] [Review][Defer] `toLocaleString()` locale-dependent number formatting — pre-existing pattern, `total_failures.toLocaleString()` renders differently per browser locale. [frontend/src/components/dashboard/StoryArcPanel.tsx:37]  — deferred, pre-existing
- [x] [Review][Defer] `recovery_rate` can theoretically exceed 100% — no model constraint prevents `recovered_count > total_subscribers` from data inconsistency. [backend/core/views/dashboard.py:69-70] — deferred, pre-existing
- [x] [Review][Defer] Frontend `recovery_action` TypeScript union vs backend string field — DB `classified_action` allows any string up to 50 chars but TS type restricts to 4 values. [frontend/src/types/dashboard.ts:6, backend model] — deferred, pre-existing

### Change Log
- 2026-04-11: Implemented Story 2.4 — Full-stack dashboard with KPI summary API, StoryArcPanel, DeclineBreakdown, UpgradeCTA. All 10 tasks complete. 150 backend tests pass (13 new), 32 frontend tests pass (18 new).
- 2026-04-11: Code review complete — 3 decision-needed, 4 patch, 3 deferred, 14 dismissed.
- 2026-04-12: All review patches applied. Story status → done.
