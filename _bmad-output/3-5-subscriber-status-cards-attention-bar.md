# Story 3.5: Subscriber Status Cards & Attention Bar

Status: review

## Story

As a founder,
I want to see subscriber recovery statuses clearly on the dashboard with immediate visibility into items requiring attention,
so that I can spot fraud flags and urgent cases without scanning the entire subscriber list.

## Acceptance Criteria

1. **Subscriber Grid with Status Cards** — Each subscriber is shown as a `SubscriberCard`: name (bold), amount (right-aligned), email sub-label, plain-language decline reason, and a status `Badge` (UX-DR9).

2. **4 Badge Variants** — Applied correctly: Recovered (green, `--accent-recovery`), Active (blue, `--accent-active`), Fraud Flagged (red, `--accent-fraud`), Passive Churn (grey, `--accent-neutral`) — each with a text label, never colour-only (FR16, UX-DR10).

3. **Attention-First Sort** — Attention-state cards (fraud flags, Supervised pending) always render first in the grid regardless of sort order.

4. **AttentionBar** — When 1+ items require the client's attention (fraud flag, supervised pending, retry cap approaching), an amber strip appears below the topbar: warning icon, "N items need your attention", "Review before next engine cycle in Xm", and named action pills (clickable chips) (UX-DR4).

5. **Pill Navigation** — Clicking an attention pill navigates to the relevant subscriber detail or review queue.

6. **Hidden When Clear** — AttentionBar is hidden when no attention items exist.

7. **Accessibility** — `role="alert"` with `aria-live="polite"` on the AttentionBar (UX-DR13).

8. **Fraud Card Styling** — Fraud-flagged subscriber cards display an amber border + "⚠ Fraud flagged" label (distinct from the red badge — amber border signals "needs attention") and appear first in the grid.

## Tasks / Subtasks

### Backend

- [x] Task 1: Create subscriber list API endpoint (AC: 1, 2, 3)
  - [x] 1.1 Create `backend/core/serializers/subscribers.py` with `SubscriberCardSerializer` — fields: `id`, `stripe_customer_id`, `email`, `status`, `decline_code`, `decline_reason` (human label), `amount_cents`, `needs_attention` (boolean), `excluded_from_automation`
  - [x] 1.2 Create `backend/core/views/subscribers.py` with `subscriber_list` GET endpoint
  - [x] 1.3 Query: `Subscriber.objects.for_account(account_id)` with annotated latest failure info (decline_code, amount_cents) via subquery from `SubscriberFailure`
  - [x] 1.4 Sorting: attention-state subscribers first (`fraud_flagged` status OR has pending action with `status=pending`), then by `updated_at` desc
  - [x] 1.5 Register route: `path("v1/subscribers/", subscriber_list, name="subscriber_list")` in `core/urls.py`
  - [x] 1.6 Tests in `backend/core/tests/test_api/test_subscribers.py`

- [x] Task 2: Create attention summary API endpoint (AC: 4, 5, 6)
  - [x] 2.1 Add `attention_items` list to the existing `dashboard_summary` response OR create a new lightweight endpoint `GET /api/v1/dashboard/attention/`
  - [x] 2.2 Each attention item: `{ type: "fraud_flag" | "pending_action" | "retry_cap", subscriber_id: int, subscriber_name: string, label: string }`
  - [x] 2.3 Sources: fraud-flagged subscribers (status=`fraud_flagged`), pending actions (Supervised mode, status=`pending`), retry cap approaching (failures where `retry_count >= retry_cap - 1` from rules)
  - [x] 2.4 Update `DashboardSummarySerializer` to include `attention_items` field
  - [x] 2.5 Tests for attention item aggregation

### Frontend

- [x] Task 3: Create TypeScript types (AC: 1, 2)
  - [x] 3.1 Create `frontend/src/types/subscriber.ts` with `SubscriberCard` interface: `id`, `stripe_customer_id`, `email`, `status` (union: `'active' | 'recovered' | 'passive_churn' | 'fraud_flagged'`), `decline_code`, `decline_reason`, `amount_cents`, `needs_attention`, `excluded_from_automation`
  - [x] 3.2 Create `AttentionItem` interface in `frontend/src/types/dashboard.ts`: `type`, `subscriber_id`, `subscriber_name`, `label`
  - [x] 3.3 Update `DashboardSummary` interface to include `attention_items: AttentionItem[]`

- [x] Task 4: Create `useSubscribers` hook (AC: 1, 3)
  - [x] 4.1 Create `frontend/src/hooks/useSubscribers.ts` — TanStack Query hook, `GET /api/v1/subscribers/`, queryKey `["subscribers"]`, `refetchInterval: 5 * 60 * 1000`

- [x] Task 5: Build `StatusBadge` component (AC: 2)
  - [x] 5.1 Create `frontend/src/components/subscriber/StatusBadge.tsx`
  - [x] 5.2 4 variants with correct colors: Recovered (green `--accent-recovery`), Active (blue `--accent-active`), Fraud Flagged (red `--accent-fraud`), Passive Churn (grey `--accent-neutral`)
  - [x] 5.3 Always render text label alongside color — never color-only
  - [x] 5.4 Font: Inter 500 (Medium), 11-12px per UX spec
  - [x] 5.5 Include `aria-label` with full status text

- [x] Task 6: Build `SubscriberCard` component (AC: 1, 2, 3, 8)
  - [x] 6.1 Create `frontend/src/components/dashboard/SubscriberCard.tsx`
  - [x] 6.2 Layout: top row = name (bold) + amount (right-aligned); sub-label = email; bottom row = plain-language decline reason + StatusBadge
  - [x] 6.3 States: Default, Hover (border darkens), Attention (amber border + "⚠" prefix on reason text), Recovered (green amount)
  - [x] 6.4 Fraud-flagged cards: amber border + "⚠ Fraud flagged" label
  - [x] 6.5 Clicking opens subscriber detail (future story — wire to navigation or noop for now)

- [x] Task 7: Build `SubscriberGrid` component (AC: 1, 3)
  - [x] 7.1 Create `frontend/src/components/dashboard/SubscriberGrid.tsx`
  - [x] 7.2 Renders list of SubscriberCard components
  - [x] 7.3 Client-side sorting guarantee: attention-state cards first (fraud_flagged status, needs_attention=true), then rest by status
  - [x] 7.4 Loading skeleton state (`SubscriberGridSkeleton`)

- [x] Task 8: Build `AttentionBar` component (AC: 4, 5, 6, 7)
  - [x] 8.1 Create `frontend/src/components/dashboard/AttentionBar.tsx`
  - [x] 8.2 Amber strip below topbar: warning icon (left), "N items need your attention" (bold, dark amber), "Review before next engine cycle in Xm" (lighter amber), action pills (right)
  - [x] 8.3 Action pills: named clickable chips, one per attention item — clicking navigates to relevant subscriber or review queue
  - [x] 8.4 Hidden when `attention_items` is empty
  - [x] 8.5 `role="alert"` with `aria-live="polite"` for accessibility
  - [x] 8.6 States: Visible (1+ items), Hidden (0 items), Urgent (fraud flag present — slightly deeper amber)

- [x] Task 9: Integrate into Dashboard page (AC: all)
  - [x] 9.1 Add `AttentionBar` to dashboard layout — renders between NavBar and main content (conditionally)
  - [x] 9.2 Add `SubscriberGrid` below existing StoryArcPanel and DeclineBreakdown sections
  - [x] 9.3 Wire `useSubscribers` hook data into SubscriberGrid
  - [x] 9.4 Wire attention items from `useDashboardSummary` into AttentionBar
  - [x] 9.5 Calculate "next engine cycle" countdown from `account.next_scan_at`

- [x] Task 10: Frontend tests (AC: all)
  - [x] 10.1 `frontend/src/__tests__/SubscriberCard.test.tsx` — renders all 4 status variants, attention styling, fraud amber border
  - [x] 10.2 `frontend/src/__tests__/AttentionBar.test.tsx` — renders when items exist, hidden when empty, correct pill rendering, accessibility attributes
  - [x] 10.3 `frontend/src/__tests__/StatusBadge.test.tsx` — all 4 variants with correct colors and text labels

## Dev Notes

### Architecture & Patterns

- **API field naming:** ALL API fields use snake_case in both Django responses AND TypeScript types. No transformation layer. TypeScript types mirror the API contract exactly.
- **Component naming:** PascalCase files (`SubscriberCard.tsx`), camelCase hooks (`useSubscribers.ts`)
- **Component location:** `SubscriberCard`, `SubscriberGrid`, `AttentionBar` in `frontend/src/components/dashboard/`. `StatusBadge` in `frontend/src/components/subscriber/`.
- **Hook pattern:** Follow existing `useDashboardSummary.ts` pattern — TanStack Query with axios, queryKey array, refetchInterval
- **Error format:** `{ "error": { "code": "...", "message": "...", "field": null } }` — never raw Django 500
- **Tenant isolation:** All backend queries MUST use `.for_account(account_id)` from `TenantScopedModel` manager — never raw `.objects.all()`

### Existing Code to Reuse (DO NOT REINVENT)

- **`KPICard.tsx`** (`frontend/src/components/dashboard/KPICard.tsx`) — reference for CSS custom property usage (`var(--accent-recovery)`, etc.) and `aria-label` patterns
- **`useDashboardSummary.ts`** — hook pattern to follow (TanStack Query, axios, queryKey)
- **`useEngineStatus.ts`** — for getting `next_scan_at` for the AttentionBar countdown
- **`DashboardSummarySerializer`** (`backend/core/serializers/dashboard.py`) — extend with `attention_items` or create adjacent serializer
- **`dashboard_summary` view** (`backend/core/views/dashboard.py`) — reference for cache patterns, account resolution, serializer usage
- **`PendingAction` model** (`backend/core/models/pending_action.py`) — query for supervised pending attention items
- **`DECLINE_CODE_LABELS`** (`backend/core/engine/labels.py`) — use for `decline_reason` human-readable text on subscriber cards. DO NOT create a new label mapping.
- **`cn()` utility** from `@/lib/utils` — for conditional className merging (used throughout codebase)
- **Design tokens** already defined in CSS: `--accent-recovery` (green), `--accent-active` (blue), `--accent-fraud` (red), `--accent-neutral` (grey), `--sn-border`, `--bg-surface`, `--text-primary`, `--text-secondary`

### Backend Model Context

- **Subscriber model** (`backend/core/models/subscriber.py`): has `status` FSMField with 4 states: `active`, `recovered`, `passive_churn`, `fraud_flagged`. Has `email`, `stripe_customer_id`, `excluded_from_automation`, `last_payment_method_fingerprint`.
- **SubscriberFailure model**: has `decline_code`, `amount_cents`, `retry_count`, `last_retry_at`, `next_retry_at`, `classified_action`, `payment_intent_id`.
- **PendingAction model**: has `subscriber` FK, `failure` FK, `recommended_action`, `status` (pending/approved/excluded).
- **TenantScopedModel base**: provides `account` FK and `for_account(id)` manager method. All models inherit from this.
- **No `subscribers.py` view or serializer exists yet** — you must create both from scratch.

### Frontend Architecture Context

- **State management:** TanStack Query for server state, Zustand for client state (batch selection, active subscriber ID)
- **Routing:** Next.js App Router. Dashboard at `frontend/src/app/(dashboard)/dashboard/page.tsx`. All dashboard pages use `(dashboard)` route group layout.
- **NavBar** already includes engine status indicator and pending action count badge for review queue.
- **AttentionBar placement:** Between `<NavBar />` and page content in the dashboard layout. Check `frontend/src/app/(dashboard)/layout.tsx` for correct insertion point.
- **No subscriber detail sheet exists yet** — clicking a SubscriberCard should be a noop or `console.log` for now (Story 5.1 covers subscriber detail panel).

### Testing Standards

- **Backend:** pytest with Django test client. Follow patterns in `backend/core/tests/test_api/test_batch.py` and `test_dpa.py` — use `APIClient`, create test users/accounts, assert response structure.
- **Frontend:** Vitest + React Testing Library. Follow patterns in `frontend/src/__tests__/ActivateEngineCTA.test.tsx` and `BatchActionToolbar.test.tsx` — mock hooks, render components, assert DOM output.

### Previous Story Intelligence (Stories 3.1–3.4)

- Stories 3.1–3.4 established: DPA acceptance flow, engine mode selection, FSM status machine, recovery engine with rule execution, card update detection, supervised mode with pending action queue and batch approval.
- The `PendingAction` model and batch action endpoints already exist and work.
- The `excluded_from_automation` field on Subscriber is already in place.
- Engine status indicator and mode switching are already implemented in the NavBar and Settings page.
- The review queue page (`/review-queue`) already exists with batch action toolbar.

### Git Intelligence

- Recent commits show pattern: backend + frontend changes in single commits per story.
- Poetry is the Python package manager — use `poetry add` for any new dependencies (unlikely needed for this story).
- No new Python dependencies should be needed — all required libs (DRF, django-fsm, etc.) are already installed.

### Project Structure Notes

- Backend: `backend/core/views/subscribers.py` (new), `backend/core/serializers/subscribers.py` (new), tests in `backend/core/tests/test_api/test_subscribers.py` (new)
- Frontend: `frontend/src/components/dashboard/SubscriberCard.tsx` (new), `frontend/src/components/dashboard/SubscriberGrid.tsx` (new), `frontend/src/components/dashboard/AttentionBar.tsx` (new), `frontend/src/components/subscriber/StatusBadge.tsx` (new), `frontend/src/hooks/useSubscribers.ts` (new), `frontend/src/types/subscriber.ts` (new)
- Modified: `backend/core/urls.py` (add subscriber list route), `backend/core/serializers/dashboard.py` (add attention_items), `backend/core/views/dashboard.py` (compute attention items), `frontend/src/types/dashboard.ts` (add AttentionItem type), `frontend/src/app/(dashboard)/dashboard/page.tsx` (integrate SubscriberGrid + AttentionBar)

### References

- [Source: _bmad-output/epics.md#Story 3.5] — Full acceptance criteria and BDD scenarios
- [Source: _bmad-output/architecture.md#API & Communication Patterns] — REST patterns, error format, endpoint naming
- [Source: _bmad-output/architecture.md#Frontend Architecture] — Component organization, hook patterns, state management
- [Source: _bmad-output/architecture.md#Naming Patterns] — snake_case API fields, PascalCase components
- [Source: _bmad-output/ux-design-specification.md#AttentionBar] — Anatomy, states, behavior
- [Source: _bmad-output/ux-design-specification.md#SubscriberCard] — Anatomy, states, behavior
- [Source: _bmad-output/ux-design-specification.md#Accessibility Considerations] — Color-blind safe, aria-labels, focus states
- [Source: _bmad-output/prd.md#FR16] — 4-status subscriber management requirement

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- No blocking issues encountered during implementation.

### Completion Notes List
- Backend: Created subscriber list API (`GET /api/v1/subscribers/`) with tenant-scoped queries, attention-first sorting (fraud_flagged + pending actions first), and human-readable decline reasons via DECLINE_CODE_LABELS.
- Backend: Extended dashboard summary API with `attention_items` field aggregating fraud flags, pending actions, and retry-cap-approaching subscribers.
- Frontend: Built StatusBadge (4 color variants with text labels + aria-labels), SubscriberCard (name/amount/email/decline-reason layout with fraud amber border), SubscriberGrid (responsive 3-col grid with attention-first client-side sorting + skeleton loader), and AttentionBar (conditional amber strip with countdown + action pills + role="alert" accessibility).
- Frontend: Integrated AttentionBar into dashboard layout between NavBar and content; SubscriberGrid added below DeclineBreakdown.
- Frontend: DashboardAttentionBar wrapper component created to bridge server-component layout with client-side data hooks.
- Tests: 11 backend tests (subscriber list API), 5 backend tests (attention items on dashboard), 19 frontend tests (StatusBadge, SubscriberCard, AttentionBar). All pass. No regressions introduced (pre-existing failures in NavBar, ProfileComplete, and billing_webhook tests are unrelated).
- Implementation date: 2026-04-15

### Change Log
- 2026-04-15: Implemented Story 3.5 — Subscriber Status Cards & Attention Bar (all 10 tasks)

### File List
**New files:**
- backend/core/serializers/subscribers.py
- backend/core/views/subscribers.py
- backend/core/tests/test_api/test_subscribers.py
- frontend/src/types/subscriber.ts
- frontend/src/hooks/useSubscribers.ts
- frontend/src/components/subscriber/StatusBadge.tsx
- frontend/src/components/dashboard/SubscriberCard.tsx
- frontend/src/components/dashboard/SubscriberGrid.tsx
- frontend/src/components/dashboard/AttentionBar.tsx
- frontend/src/components/dashboard/DashboardAttentionBar.tsx
- frontend/src/__tests__/StatusBadge.test.tsx
- frontend/src/__tests__/SubscriberCard.test.tsx
- frontend/src/__tests__/AttentionBar.test.tsx

**Modified files:**
- backend/core/urls.py (added subscriber list route)
- backend/core/serializers/dashboard.py (added AttentionItemSerializer + attention_items field)
- backend/core/views/dashboard.py (added attention_items computation)
- backend/core/tests/test_api/test_dashboard.py (added attention_items tests)
- frontend/src/types/dashboard.ts (added AttentionItem interface + attention_items to DashboardSummary)
- frontend/src/app/(dashboard)/layout.tsx (added DashboardAttentionBar)
- frontend/src/app/(dashboard)/dashboard/page.tsx (integrated SubscriberGrid)
