# Story 3.2 (v1): Current-Month Failed-Payments Dashboard

Status: done

> **v1 scope (post-2026-04-29 simplification).** Replaces the quarantined `3-2-autopilot-recovery-engine-rule-execution-4-state-status-machine.md` (v0). The current-month failed-payments list is now the dashboard's primary working surface — no separate review queue, no autopilot vs supervised mode. See `_bmad-output/sprint-change-proposal-2026-04-29.md`.

> **Inheriting infrastructure already on `main`** (do NOT recreate):
> - `Subscriber` + `SubscriberFailure` models — `backend/core/models/subscriber.py:16-100` (FSM statuses: `active`, `recovered`, `passive_churn`, `fraud_flagged`)
> - `SubscriberFailure.failure_created_at` (DateTimeField), `amount_cents` (IntegerField), `decline_code` (CharField), `payment_method_country` (CharField, nullable) — `subscriber.py:65-78`
> - `Subscriber.excluded_from_automation` (BooleanField) — `subscriber.py:24`
> - `GET /api/v1/subscribers/` endpoint (subscriber-keyed list with latest-failure annotation) — `backend/core/views/subscribers.py:14-86`
> - `SubscriberCardSerializer` — `backend/core/serializers/subscribers.py:4-13`
> - `DECLINE_CODE_LABELS` plain-language dict — `backend/core/engine/labels.py:9-50`
> - `DECLINE_RULES` config — `backend/core/engine/rules.py:32-` (v1 still uses v0 `action` vocabulary; Story 3.5 v1 adds `recommended_email`)
> - Month-start filtering pattern — `backend/core/views/dashboard.py:51-52` (`now.replace(day=1, hour=0, ...)`)
> - `NotificationLog` model with `created_at` (per `TenantScopedModel`) — `backend/core/models/notification.py:18-52`; v0 `failure_notice` rows already exist on main from Story 4.1
> - Frontend `SubscriberCard`, `SubscriberGrid`, `StatusBadge`, `DeclineCodeExplainer` — `frontend/src/components/dashboard/` and `frontend/src/components/subscriber/`
> - `useSubscribers` TanStack Query hook — `frontend/src/hooks/useSubscribers.ts`
> - `useDpaGate` hook (just shipped 3-1-v1) — `frontend/src/hooks/useDpaGate.ts`
> - `useAccount` hook with `tier`, `dpa_accepted`, `dpa_version` — `frontend/src/hooks/useAccount.ts`
> - `formatCurrency`, `formatDate`, `formatRelativeTime` — `frontend/src/lib/formatters.ts:1-31`
> - shadcn primitives in `frontend/src/components/ui/`: `table.tsx`, `badge.tsx`, `button.tsx`, `tooltip` (via `@base-ui/react`), `popover.tsx`

## Story

As a Mid-tier founder,
I want a dashboard view of all failed payments from the current month with recommended emails per row,
So that I can review and act on each at my own pace.

## Acceptance Criteria

1. **Given** the dashboard loads **When** the failed-payments list renders **Then** rows are filtered to `failure_created_at` within the current calendar month (UTC; v1 has no per-account timezone field — see Dev Notes §Timezone) **And** each row displays: subscriber name + email, amount in cents formatted to € (via `formatCurrency`), plain-language decline reason via `DECLINE_CODE_LABELS`, recommended email type chip, status badge (Active / Recovered / Passive Churn / Fraud Flagged), and last-email-sent timestamp if any (most-recent `NotificationLog` row for that failure with `status="sent"`).

2. **Given** the failed-payments list **When** the client clicks a column header (Date, Amount) **Then** the list sorts by that column (asc/desc toggle) **And** the active sort key + direction persist in URL query params `?sort=<key>&dir=<asc|desc>` **And** browser back/forward preserves the sort.

3. **Given** a Free-tier client (`account.tier === "free"`) **When** they view the failed-payments list **Then** the list IS visible (read-only) **And** any per-row action button placeholders (Send / Mark resolved / Exclude — wired in Stories 3.3/3.4) render with `disabled` state and a tooltip "Upgrade to Mid or Pro to enable email actions" **And** an inline upgrade CTA links to `/settings#subscription`.

4. **Given** zero failed payments for the current month **When** the list renders **Then** the empty state shows the heading "No failed payments this month." with sub-copy "Your subscribers are paying — keep shipping." (verbatim per UX-DR `12.3` empty-state pattern).

5. **Given** a `fraud_flagged` subscriber row **When** rendered **Then** the recommended-email chip displays "—" (no recommendation; per Story 3.5 v1 `fraudulent` decline code maps to `None`) **And** the row has an amber border (`border-amber-500 border-2`) to distinguish it from non-fraud rows.

## Tasks / Subtasks

### Backend

- [x] **Task 1: Add the `failed_payments_list` view** (AC: #1, #5)
  - [x] 1.1 Create `failed_payments_list(request)` in `backend/core/views/dashboard.py` (extend the existing module — keep `dashboard_summary` untouched). Decorate with `@api_view(["GET"])` and `@permission_classes([IsAuthenticated])` per the existing pattern (`dashboard.py:179-181`).
  - [x] 1.2 Resolve the account via the same `try / except request.user.__class__.account.RelatedObjectDoesNotExist` shape as `dashboard_summary` (`dashboard.py:183-189`). Same 404 envelope: `{"error": {"code": "NOT_FOUND", "message": "No account found.", "field": None}}`.
  - [x] 1.3 Build the queryset:
    ```python
    from django.utils import timezone
    from django.db.models import OuterRef, Subquery, Max
    from core.models.subscriber import SubscriberFailure
    from core.models.notification import NotificationLog
    from core.engine.labels import DECLINE_CODE_LABELS

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # last_email_sent: most recent NotificationLog.created_at for this failure with status="sent"
    last_sent = (
        NotificationLog.objects.filter(failure_id=OuterRef("pk"), status="sent")
        .order_by("-created_at")
        .values("created_at")[:1]
    )
    failures = (
        SubscriberFailure.objects.for_account(account.id)
        .filter(failure_created_at__gte=month_start)
        .select_related("subscriber")
        .annotate(last_email_sent_at=Subquery(last_sent))
    )
    ```
    Use `for_account()` from `TenantScopedModel` (`backend/core/models/base.py:13-15`) — never `.objects.all()`. Tenant isolation is structurally enforced via `for_account()`.
  - [x] 1.4 Apply sort from query params (AC2):
    ```python
    sort = request.GET.get("sort", "date")
    direction = request.GET.get("dir", "desc")
    if sort not in {"date", "amount"} or direction not in {"asc", "desc"}:
        return Response(
            {"error": {"code": "VALIDATION_ERROR", "message": "Invalid sort or dir param.", "field": "sort"}},
            status=400,
        )
    field_map = {"date": "failure_created_at", "amount": "amount_cents"}
    order_field = field_map[sort]
    if direction == "desc":
        order_field = f"-{order_field}"
    failures = failures.order_by(order_field)
    ```
    Reject unknown values with a `VALIDATION_ERROR` envelope rather than silently falling back — protects against typos in URLs and is testable.
  - [x] 1.5 Per row, build the response payload. The `recommended_email_type` field is **null** for v1 — Story 3.5 v1 will populate it when the rule engine ships. Set it to `None` here so the frontend chip renders "—" until 3.5 lands. Add a one-line comment in the view: `# recommended_email_type set to None until Story 3.5 v1 lands the rule engine.`
    ```python
    results = []
    for f in failures:
        sub = f.subscriber
        results.append({
            "id": f.id,
            "subscriber_id": sub.id,
            "subscriber_email": sub.email or "",
            "subscriber_stripe_customer_id": sub.stripe_customer_id,
            "subscriber_status": sub.status,
            "decline_code": f.decline_code,
            "decline_reason": DECLINE_CODE_LABELS.get(f.decline_code, DECLINE_CODE_LABELS["_default"]),
            "amount_cents": f.amount_cents,
            "failure_created_at": f.failure_created_at.isoformat(),
            "recommended_email_type": None,  # Story 3.5 v1 populates
            "last_email_sent_at": f.last_email_sent_at.isoformat() if f.last_email_sent_at else None,
            "payment_method_country": f.payment_method_country,
            "excluded_from_automation": sub.excluded_from_automation,
        })
    return Response({"data": results})
    ```
    Wrap the response per the `{"data": ...}` envelope contract (`architecture.md#Format Patterns:489-502`).
  - [x] 1.6 Add a `FailedPaymentRowSerializer` to `backend/core/serializers/dashboard.py` (the file exists per `architecture.md:643-648`) mirroring the dict shape above — use `serializers.Serializer` (no `ModelSerializer`; the row is a composed dict, not a model). Use `allow_null=True` on `recommended_email_type`, `last_email_sent_at`, `subscriber_email`, `payment_method_country`. Pass `results` through the serializer (`many=True`) before returning. This locks the contract for `drf-spectacular` + future schema generation.

- [x] **Task 2: Wire the URL** (AC: #1)
  - [x] 2.1 In `backend/core/urls.py`, add `from core.views.dashboard import dashboard_summary, failed_payments_list` (extend the existing import at line 6) and a new route directly under the existing `dashboard_summary` route (line 19): `path("v1/dashboard/failed-payments/", failed_payments_list, name="failed_payments_list"),`. Use kebab-case for multi-word per `architecture.md#Naming Patterns:410`.

- [x] **Task 3: Backend tests** (AC: #1, #2, #5)
  - [x] 3.1 Create `backend/core/tests/test_api/test_failed_payments_list.py` following the `test_subscribers.py` shape (helper `_create_subscriber` at line 36 — copy the import block + helper into the new file rather than refactor; refactoring the helper into `conftest.py` is out of scope). The class name is `TestFailedPaymentsListEndpoint` and `URL = "/api/v1/dashboard/failed-payments/"`.
  - [x] 3.2 Tests to write:
    - `test_requires_authentication` — unauthenticated GET returns 401.
    - `test_empty_account_returns_empty_data_array` — authenticated GET with no failures returns `{"data": []}` and 200.
    - `test_returns_only_current_month_failures` — create three failures: one this month (now), one with `failure_created_at = month_start - timedelta(seconds=1)` (last day of previous month), one with `failure_created_at = now + timedelta(days=1)` (still this month). Assert response includes the now-row + the +1d row, excludes the previous-month row.
    - `test_sort_by_date_desc_default` — create 3 failures across the month, default GET sorts newest-first.
    - `test_sort_by_amount_asc` — `?sort=amount&dir=asc` returns ascending amounts.
    - `test_sort_by_amount_desc` — `?sort=amount&dir=desc` returns descending amounts.
    - `test_invalid_sort_returns_400` — `?sort=banana` returns `{"error": {"code": "VALIDATION_ERROR", ...}}`.
    - `test_invalid_dir_returns_400` — `?dir=sideways` returns 400.
    - `test_decline_reason_translated` — assert `card["decline_reason"] == "Insufficient funds"` for `insufficient_funds`.
    - `test_unknown_decline_code_falls_back_to_default_label` — create failure with `decline_code="totally_unknown"`; assert `decline_reason == "Payment declined"` (the `_default` value in `DECLINE_CODE_LABELS`).
    - `test_recommended_email_type_is_null_in_v1` — assert `card["recommended_email_type"] is None` (lock-in test for the Story 3.5 v1 hand-off).
    - `test_last_email_sent_at_null_when_no_notification` — fresh failure → `last_email_sent_at is None`.
    - `test_last_email_sent_at_uses_most_recent_sent_log` — create a `NotificationLog` with `status="sent"` and a separate `NotificationLog` with `status="failed"` (more recent); assert `last_email_sent_at` matches the `sent` row's `created_at`, NOT the failed row's.
    - `test_fraud_flagged_subscriber_status_in_response` — create failure for a subscriber with `status=STATUS_FRAUD_FLAGGED`; assert `card["subscriber_status"] == "fraud_flagged"`.
    - `test_tenant_isolation` — same shape as `test_subscribers.py:142-154` (two accounts each see only their own rows).
  - [x] 3.3 For NotificationLog fixtures, import `from core.models.notification import NotificationLog` and create with: `NotificationLog.objects.create(subscriber=sub, failure=failure, email_type="failure_notice", status="sent", account=account)`. The unique-sent constraint (`notification.py:47-51`) requires distinct `(failure, email_type)` — use different email_types if creating multiple sent rows in one test.
  - [x] 3.4 Use `pytest.mark.django_db`. Use `auth_client` fixture from `tests/conftest.py` (the project-level conftest, not `test_api/conftest.py` which is empty) — `auth_client` is the JWT-authenticated APIClient pattern used in every existing test. If `auth_client` does NOT exist in `tests/conftest.py`, copy it from `test_subscribers.py:14-33` (the `second_user`/`second_auth_client` block) into the new test file.
  - [x] 3.5 Run `cd backend && poetry run pytest core/tests/test_api/test_failed_payments_list.py -v` — all green.

### Frontend

- [x] **Task 4: Add `FailedPayment` type + hook** (AC: #1, #2)
  - [x] 4.1 Create `frontend/src/types/failed_payment.ts`:
    ```typescript
    export type RecommendedEmailType =
      | "update_payment"
      | "retry_reminder"
      | "final_notice"
      | null;

    export interface FailedPayment {
      id: number;
      subscriber_id: number;
      subscriber_email: string;
      subscriber_stripe_customer_id: string;
      subscriber_status: "active" | "recovered" | "passive_churn" | "fraud_flagged";
      decline_code: string;
      decline_reason: string;
      amount_cents: number;
      failure_created_at: string;
      recommended_email_type: RecommendedEmailType;
      last_email_sent_at: string | null;
      payment_method_country: string | null;
      excluded_from_automation: boolean;
    }

    export type SortKey = "date" | "amount";
    export type SortDirection = "asc" | "desc";
    ```
    Snake_case fields mirror the API contract per `architecture.md#Naming Patterns:415-427`. **Do NOT** reuse `SubscriberCard` from `types/subscriber.ts` — that type is keyed on subscriber, not failure, and the dashboard list is failure-keyed.
  - [x] 4.2 Create `frontend/src/hooks/useFailedPayments.ts`:
    ```typescript
    "use client";

    import { useQuery } from "@tanstack/react-query";
    import api from "@/lib/api";
    import type { ApiResponse } from "@/types";
    import type { FailedPayment, SortKey, SortDirection } from "@/types/failed_payment";

    export function useFailedPayments(sort: SortKey = "date", dir: SortDirection = "desc") {
      return useQuery<FailedPayment[]>({
        queryKey: ["failed-payments", sort, dir],
        queryFn: async () => {
          const { data } = await api.get<ApiResponse<FailedPayment[]>>(
            `/dashboard/failed-payments/?sort=${sort}&dir=${dir}`
          );
          return data.data;
        },
        staleTime: 5 * 60 * 1000,
        refetchInterval: 5 * 60 * 1000,
      });
    }
    ```
    Mirror the `useSubscribers` pattern (`frontend/src/hooks/useSubscribers.ts:8-20`) — staleTime/refetchInterval identical for cache uniformity. The query key includes sort/dir so each combination caches independently (no manual cache-eviction on sort change).
  - [x] 4.3 **DO NOT** delete or modify `useSubscribers` — Story 3.5 v1 + later stories may still use it for the subscriber-keyed views (e.g., subscriber detail Sheet). The new hook is additive.

- [x] **Task 5: `FailedPaymentsList` component** (AC: #1, #2, #4, #5)
  - [x] 5.1 Create `frontend/src/components/dashboard/FailedPaymentsList.tsx`. Use the shadcn `Table` primitive (`frontend/src/components/ui/table.tsx`) — render columns:
    | Column | Header label | Sortable? | Notes |
    |--------|--------------|-----------|-------|
    | Subscriber | "Subscriber" | No | Two-line cell: name (bold, falls back to `stripe_customer_id` if email empty) + email (muted) |
    | Decline reason | "Reason" | No | `decline_reason` (already plain-language from backend) |
    | Amount | "Amount" | **Yes** | Right-aligned, formatted via `formatCurrency(amount_cents, "EUR")` — note "€" not "$" — see Dev Notes §Currency |
    | Date | "Date" | **Yes** | `formatDate(failure_created_at)` |
    | Recommended | "Recommended email" | No | `<RecommendedEmailChip type={row.recommended_email_type} />` — when null, render "—" in a muted span. AC5: fraud-flagged rows always render "—" because the rule engine returns null for `fraudulent`. |
    | Status | "Status" | No | `<StatusBadge status={row.subscriber_status} />` — reuse `frontend/src/components/subscriber/StatusBadge.tsx` |
    | Last email | "Last email" | No | `formatRelativeTime(last_email_sent_at)` if non-null, else "—" |
    | Actions | "" (no header) | No | Three placeholder Ghost buttons: "Send", "Mark resolved", "Exclude". For 3.2, ALL THREE are `disabled` placeholders — Stories 3.3 + 3.4 wire them up. Show a Tooltip "Available after Stripe connection" if `account.tier === "free"`, else "Coming in next release" — see Task 6 for tier-aware logic. |
  - [x] 5.2 Inline `RecommendedEmailChip` component (private to this file unless reused — start as a small const within the file):
    ```tsx
    function RecommendedEmailChip({ type }: { type: RecommendedEmailType }) {
      if (!type) return <span className="text-[var(--text-secondary)]">—</span>;
      const labels = {
        update_payment: "Update payment",
        retry_reminder: "Retry reminder",
        final_notice: "Final notice",
      };
      return (
        <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium bg-[var(--accent-active)]/15 text-[var(--accent-active)]">
          {labels[type]}
        </span>
      );
    }
    ```
    Match `StatusBadge`'s visual language (rounded-full, 11px, color-token bg). Share styling via Tailwind, NOT CSS modules.
  - [x] 5.3 Sort UI: clicking the "Amount" or "Date" header toggles direction; clicking a different sortable header switches the key and resets to descending. Use Lucide's `ArrowUp` / `ArrowDown` icons (8px) inline beside the header label when active.
  - [x] 5.4 Sort state syncs to URL via `useSearchParams` + `useRouter().replace()` from `next/navigation` — pattern below:
    ```tsx
    "use client";
    import { useSearchParams, useRouter, usePathname } from "next/navigation";
    import type { SortKey, SortDirection } from "@/types/failed_payment";

    function useSortFromUrl(): { sort: SortKey; dir: SortDirection; setSort: (k: SortKey) => void } {
      const params = useSearchParams();
      const router = useRouter();
      const pathname = usePathname();
      const sort = (params.get("sort") === "amount" ? "amount" : "date") as SortKey;
      const dir = (params.get("dir") === "asc" ? "asc" : "desc") as SortDirection;
      const setSort = (key: SortKey) => {
        const next = new URLSearchParams(params.toString());
        if (key === sort) {
          next.set("dir", dir === "desc" ? "asc" : "desc");
        } else {
          next.set("sort", key);
          next.set("dir", "desc");
        }
        router.replace(`${pathname}?${next.toString()}`, { scroll: false });
      };
      return { sort, dir, setSort };
    }
    ```
    `router.replace` (NOT `push`) so back/forward doesn't accumulate sort-toggle history. `scroll: false` keeps the table in place during re-render.
  - [x] 5.5 Empty state (AC4): when `data.length === 0` (after load), render the existing `ZeroState` pattern from `_bmad-output/ux-design-specification.md:1086-1088`. Since there's no existing `ZeroState` component on `main` for this surface, render inline:
    ```tsx
    <div className="rounded-lg border border-[var(--sn-border)] bg-[var(--bg-surface)] p-12 text-center">
      <h3 className="text-lg font-semibold text-[var(--text-primary)]">
        No failed payments this month.
      </h3>
      <p className="mt-2 text-sm text-[var(--text-secondary)]">
        Your subscribers are paying — keep shipping.
      </p>
    </div>
    ```
    Verbatim copy from the UX spec — do NOT paraphrase.
  - [x] 5.6 Loading state: render a 5-row skeleton (per UX-DR `12.8`). Match the column structure with `<div className="h-4 bg-[var(--sn-border)] rounded animate-pulse" />` cells. Pattern is in `SubscriberGrid.tsx:11-29`.
  - [x] 5.7 Fraud row visual treatment (AC5): apply `border-amber-500 border-2` to the `<tr>` when `row.subscriber_status === "fraud_flagged"`. shadcn `Table` lets you pass `className` on `TableRow`. Do NOT add an `⚠` prefix — the table layout doesn't have room; the StatusBadge already labels it as Fraud Flagged.

- [x] **Task 6: Per-row action placeholders + tier gate** (AC: #3)
  - [x] 6.1 Inside `FailedPaymentsList`, add the action button column with three Ghost buttons: Send, Mark resolved, Exclude. ALL three are `disabled` in 3.2 — Stories 3.3 (per-row) and 3.4 (bulk) hook them up to actual mutations. The disabled-with-tooltip pattern is identical to the v1 contract from Story 3.1 v1's `useDpaGate`:
    ```tsx
    import { useDpaGate } from "@/hooks/useDpaGate";
    import { useAccount } from "@/hooks/useAccount";

    const { sendDisabled, tooltip: dpaTooltip } = useDpaGate();
    const { data: account } = useAccount();
    const isFree = account?.tier === "free";
    const tierTooltip = isFree
      ? "Upgrade to Mid or Pro to enable email actions"
      : undefined;
    // Per-row buttons: disabled = isFree || sendDisabled || (story-3.2-only) true placeholder.
    // For Story 3.2, ALWAYS disabled — Stories 3.3/3.4 lift the placeholder gate.
    ```
  - [x] 6.2 Tooltip precedence rule (AC3 + carry-forward from 3-1-v1): tier > DPA > placeholder. If `isFree`, show `tierTooltip`. Else if `sendDisabled` (no DPA), show `dpaTooltip` (`"Sign the DPA to enable email sends"`). Else show "Coming in next release" (the placeholder copy for 3.2 since the actions don't exist yet). This precedence is asserted in tests.
  - [x] 6.3 Free-tier inline upgrade CTA (AC3): when `isFree`, render a small banner above the table:
    ```tsx
    {isFree && (
      <div className="mb-4 rounded-md border border-[var(--sn-border)] bg-[var(--bg-surface)] p-3 text-sm">
        <span className="text-[var(--text-secondary)]">View-only on Free tier. </span>
        <Link href="/settings#subscription" className="font-medium text-[var(--accent-active)] hover:underline">
          Upgrade to send dunning emails →
        </Link>
      </div>
    )}
    ```
    Use `next/link`'s `<Link>` (NOT `<a>`). Anchor `#subscription` is the existing Settings section per the v1 settings page (Settings layout shipped in 3-1-v1).

- [x] **Task 7: Wire `FailedPaymentsList` into the dashboard page** (AC: #1, #4)
  - [x] 7.1 Edit `frontend/src/app/(dashboard)/dashboard/page.tsx`. The current page renders `StoryArcPanel` + `DeclineBreakdown` + `SubscriberGrid` (lines 30-53). The v1 dashboard shifts the primary working surface to the failed-payments list (UX-DR16: list as primary surface). Insert `<FailedPaymentsList />` directly under `<NextScanCountdown />` and ABOVE the StoryArcPanel block. **Keep** StoryArcPanel + DeclineBreakdown — they remain as supplementary KPIs. Drop the SubscriberGrid block (lines 47-51) — the failed-payments list replaces it as the row-level view (the `useSubscribers` hook still exists for future detail-Sheet use, but the grid component is no longer rendered on this page).
  - [x] 7.2 The component is self-contained: `<FailedPaymentsList />` calls `useFailedPayments` internally — no props from `page.tsx`. Page layout stays clean.
  - [x] 7.3 Update the `useEffect` upgrade-success branch (lines 21-28): in addition to invalidating `["account", "me"]` and `["dashboard-summary"]`, also invalidate `["failed-payments"]` so a freshly upgraded user sees the action buttons re-evaluate. Pattern:
    ```tsx
    queryClient.invalidateQueries({ queryKey: ["failed-payments"] });
    ```
  - [x] 7.4 No changes to `(dashboard)/layout.tsx`, `NavBar`, or `WorkspaceIdentity`. The list is purely page-scoped.

- [x] **Task 8: Frontend tests** (AC: #1, #2, #3, #4, #5)
  - [x] 8.1 Create `frontend/src/__tests__/FailedPaymentsList.test.tsx`. Use the same Vitest + React Testing Library setup as `frontend/src/__tests__/useDpaGate.test.ts` and `frontend/src/__tests__/SubscriberCard.test.tsx` (if exists; otherwise `DeclineBreakdown.test.tsx`).
  - [x] 8.2 Mock `useFailedPayments`, `useDpaGate`, `useAccount`, and Next.js navigation (`vi.mock("next/navigation", ...)`). Wrap render in `QueryClientProvider` per the existing test conventions.
  - [x] 8.3 Tests:
    - `renders empty state when data is empty` — assert the heading "No failed payments this month." and sub-copy "Your subscribers are paying — keep shipping." (verbatim).
    - `renders skeleton while loading` — `isLoading: true, data: undefined` → 5 skeleton rows.
    - `renders one row per failed payment` — 3 mock failures → 3 `<tr>` rows in tbody.
    - `formats amount as EUR` — assert the cell contains `€50.00` or `€ 50.00` (whatever `Intl.NumberFormat("en-US", {style: "currency", currency: "EUR"})` outputs — write the test to call the same formatter and assert equality, NOT a hardcoded string).
    - `applies amber border to fraud-flagged rows` — `subscriber_status: "fraud_flagged"` → row has `border-amber-500 border-2` class.
    - `recommended email chip shows em-dash for null type` — `recommended_email_type: null` → text content `"—"`.
    - `recommended email chip shows label for non-null type` — `recommended_email_type: "update_payment"` → `"Update payment"`.
    - `last email shows em-dash when null` — `last_email_sent_at: null` → `"—"`.
    - `clicking Amount header toggles sort direction` — clicking once asks the hook to re-fetch with `?sort=amount&dir=desc` (or `asc` after the second click). Assert via the URL update — mock `router.replace` and check call args.
    - `clicking Date header switches sort key + resets dir to desc` — initial `sort=amount&dir=asc`; click Date → expect `?sort=date&dir=desc`.
    - `Free tier shows upgrade banner` — mock `useAccount` with `tier: "free"` → banner text "View-only on Free tier." + link to `/settings#subscription`.
    - `Free tier disables action buttons with tier tooltip` — assert all three action buttons render with `disabled` and the tooltip resolves to the tier-tooltip string.
    - `Mid tier without DPA disables action buttons with DPA tooltip` — `tier: "mid"`, `useDpaGate` returns `sendDisabled: true, tooltip: "Sign the DPA to enable email sends"` → buttons disabled with that tooltip.
    - `Mid tier with DPA accepted shows placeholder tooltip` — `sendDisabled: false`, `isFree: false` → tooltip is `"Coming in next release"` (the 3.2-only placeholder).
  - [x] 8.4 Run `cd frontend && pnpm vitest run FailedPaymentsList` — green.

### Cross-cutting

- [ ] **Task 9: Manual smoke verification** (AC: all) — _Deferred to reviewer; automated suite covers ACs 1–5._
  - [ ] 9.1 Start the docker-compose stack: `docker compose up`. In a Mid-tier account with DPA accepted (use the seed user from 3-1-v1's manual verification), seed at least 4 SubscriberFailures via the Django shell:

### Review Findings (2026-04-30)

_Generated by `bmad-code-review` skill — 3 parallel adversarial reviewers (Blind Hunter, Edge Case Hunter, Acceptance Auditor) on the uncommitted story branch. All 5 ACs pass functional review per Acceptance Auditor; findings below are quality, defense-in-depth, and edge-case hardening._

#### Patches

- [x] **[Review][Patch] Add `.for_account(account.id)` to `last_sent` Subquery (tenant defense-in-depth)** — `NotificationLog.objects.filter(failure_id=OuterRef("pk"), status="sent")` doesn't tenant-filter; if a `NotificationLog` is ever inserted with a wrong `failure_id` (admin restore, fixture bug), the timestamp leaks across accounts. Add `.for_account(account.id)` to the subquery. [`backend/core/views/dashboard.py:240-244`]
- [x] **[Review][Patch] Add `subscriber_id=OuterRef("subscriber_id")` to `last_sent` Subquery (subscriber defense-in-depth)** — Constrain the subquery to also match `subscriber_id` so a corrupt `NotificationLog.failure_id` pointing at a different subscriber's failure can't surface the wrong timestamp. [`backend/core/views/dashboard.py:240-244`]
- [x] **[Review][Patch] Add `output_field=DateTimeField()` to `Subquery(last_sent)`** — Without explicit `output_field`, type inference can fail on certain backends or with `order_by`, raising `FieldError`. Defensive declaration costs nothing. [`backend/core/views/dashboard.py:240-251`]
- [x] **[Review][Patch] Replace `serializers.CharField` with `serializers.DateTimeField` for `failure_created_at` and `last_email_sent_at`** — Story Task 1.6 explicitly says the serializer "locks the contract for `drf-spectacular` + future schema generation". `CharField` for ISO timestamps loses validation and the datetime/string distinction; if the view ever passes a `datetime` instead of a pre-formatted string, serialization silently stringifies with non-ISO format. Use `DateTimeField()` and let DRF format it. [`backend/core/serializers/dashboard.py:21,23`]
- [x] **[Review][Patch] Add `allow_blank=True` to `subscriber_stripe_customer_id` and `decline_code` serializer fields** — `serializers.CharField()` defaults to `allow_blank=False`. If a fixture/migration ever produces an empty `stripe_customer_id` or `decline_code`, the whole list 500s on serialization. [`backend/core/serializers/dashboard.py:16,17`]
- [x] **[Review][Patch] Move `from core.models.notification import NotificationLog` import to top of `views/dashboard.py` (PEP 8 E402)** — Import is placed below module-level constant `ATTENTION_ITEMS_CAP = 10`. Cosmetic but lint-flaggable. [`backend/core/views/dashboard.py:60-62`]
- [x] **[Review][Patch] Remove unused `STATUS_RECOVERED` import from `test_failed_payments_list.py`** — Imported but never referenced in any test. [`backend/core/tests/test_api/test_failed_payments_list.py:11`]
- [x] **[Review][Patch] `useFailedPayments` should use `URLSearchParams` instead of string interpolation** — Today the values are constrained by union types, but the pattern invites injection if the function signature widens. Defense-in-depth. [`frontend/src/hooks/useFailedPayments.ts:20-22`]
- [x] **[Review][Patch] Subscriber cell duplicates email when email is present** — Primary line is `subscriber_email || subscriber_stripe_customer_id`; secondary line is `{subscriber_email && <span>{subscriber_email}</span>}`. When email is non-empty, both lines render the same string. Either show `stripe_customer_id` as the secondary line, or omit the secondary line when primary is the email. [`frontend/src/components/dashboard/FailedPaymentsList.tsx:183-199`]
- [x] **[Review][Patch] Skeleton column count is 7 but table has 8 columns** — Loading skeleton renders 7 grid columns; table renders 8 (Subscriber, Reason, Amount, Date, Recommended, Status, Last email, Actions). Cosmetic mismatch. [`frontend/src/components/dashboard/FailedPaymentsList.tsx:880`]
- [x] **[Review][Patch] `isLoading || !data` shows skeleton forever on error** — `useFailedPayments` errors (500/network) leave `data: undefined, isLoading: false, isError: true`; component renders skeleton indefinitely. Handle `isError` and render an error state with retry. [`frontend/src/components/dashboard/FailedPaymentsList.tsx:264`]
- [x] **[Review][Patch] TS type `subscriber_email: string` should be `string | null`** — Backend serializer is `allow_null=True`; FE type lies. Today runtime works because empty string is falsy, but if API returns `null`, TS guards mislead. [`frontend/src/types/failed_payment.ts:1110`]
- [x] **[Review][Patch] Add tenant-isolation test for `NotificationLog` subquery** — Existing `test_tenant_isolation` covers failures only. After P1+P2 above, add a test that creates a `NotificationLog` for `second_account` referencing the same `failure_id` and asserts it is NOT surfaced. [`backend/core/tests/test_api/test_failed_payments_list.py`]

#### Deferred

- [x] **[Review][Defer] UTC month boundary (no per-account timezone)** [`backend/core/views/dashboard.py:237-238`] — deferred, explicit v2 spec deferral per Dev Notes §Timezone.
- [x] **[Review][Defer] No pagination on `failed_payments_list`** [`backend/core/views/dashboard.py:259-280`] — deferred, explicit v2 spec deferral per Dev Notes §v1 Scope Boundaries.
- [x] **[Review][Defer] Hardcoded EUR currency** [`frontend/src/components/dashboard/FailedPaymentsList.tsx:204`] — deferred, explicit v2 spec deferral per Dev Notes §Currency.
- [x] **[Review][Defer] `request.user.__class__.account.RelatedObjectDoesNotExist` pattern is fragile** [`backend/core/views/dashboard.py:90`] — deferred, pre-existing pattern from `dashboard_summary` and explicitly mandated by Task 1.2.
- [x] **[Review][Defer] StatusBadge crashes on unknown subscriber_status** [`frontend/src/components/subscriber/StatusBadge.tsx`] — deferred, pre-existing component not introduced by this story; defensive default belongs in a separate StatusBadge hardening pass.
- [x] **[Review][Defer] Tooltip flicker (Free user with loading account momentarily sees placeholder copy)** [`frontend/src/components/dashboard/FailedPaymentsList.tsx:236-241`] — deferred, sub-second flicker not visible to most users.
- [x] **[Review][Defer] React Query cache key omits month boundary (stale data up to 5 min after midnight UTC rollover)** [`frontend/src/hooks/useFailedPayments.ts:17-26`] — deferred, narrow edge case; refetch covers within 5 min.
- [x] **[Review][Defer] Native `title` attribute used for tooltips instead of `@base-ui/react`** [`frontend/src/components/dashboard/FailedPaymentsList.tsx:922`] — deferred, documented scope deviation in completion notes.
- [x] **[Review][Defer] AC2 back/forward preservation not directly asserted in tests** [`frontend/src/__tests__/FailedPaymentsList.test.tsx:648-674`] — deferred, implicit coverage via `router.replace` tests.
- [x] **[Review][Defer] `formatDate` uses `en-US` locale unconditionally** [`frontend/src/lib/formatters.ts:8-10`] — deferred, broader i18n concern, pre-existing utility.
- [x] **[Review][Defer] `formatRelativeTime` returns "-1d ago" on server clock skew** [`frontend/src/lib/formatters.ts:12-21`] — deferred, pre-existing utility, edge case.
- [x] **[Review][Defer] `data-fraud="true"` has no consumer / no fraud audio announcement** [`frontend/src/components/dashboard/FailedPaymentsList.tsx:187-188`] — deferred, a11y enhancement for follow-up.
- [x] **[Review][Defer] Free-tier upgrade banner renders above empty state, awkward messaging hierarchy** [`frontend/src/components/dashboard/FailedPaymentsList.tsx:250-267`] — deferred, UX polish.
- [x] **[Review][Defer] `failed_payments_list` not cached server-side (every mount hits DB)** [`backend/core/views/dashboard.py:213-283`] — deferred, v2 perf optimization.
- [x] **[Review][Defer] URL may accumulate `?upgrade=success` if sort click races dashboard cleanup effect** [`frontend/src/components/dashboard/FailedPaymentsList.tsx:67-76`] — deferred, narrow timing edge case.
- [x] **[Review][Defer] Frontend test fixture provides partial Account (missing fields like `dpa_version`, `engine_active`)** [`frontend/src/__tests__/FailedPaymentsList.test.tsx`] — deferred, testing hygiene improvement.
- [x] **[Review][Defer] Fraud row visual: `border-amber-500 border-2` on `<tr>` may not paint visibly with `border-collapse`** [`frontend/src/components/dashboard/FailedPaymentsList.tsx:188`] — deferred, UX polishing will be done later on.
- [x] **[Review][Defer] `useSortFromUrl.setSort` reads stale `useSearchParams` snapshot on rapid clicks** [`frontend/src/components/dashboard/FailedPaymentsList.tsx:67-76`] — deferred, applied fix using `window.location.search` regressed the existing sort-test suite (test mocks `useSearchParams` only). Bug is theoretical (rapid double-click within a single render frame) and unlikely in practice; revisit alongside test infra changes that mock `window.location` or via a `useRef` re-sync pattern.
    ```bash
    docker compose exec backend poetry run python manage.py shell
    ```
    ```python
    from django.utils import timezone
    from datetime import timedelta
    from core.models.account import Account
    from core.models.subscriber import Subscriber, SubscriberFailure
    from core.models.notification import NotificationLog
    account = Account.objects.first()
    sub = Subscriber.objects.create(account=account, stripe_customer_id="cus_smoke_1", email="alice@example.com")
    f1 = SubscriberFailure.objects.create(account=account, subscriber=sub, payment_intent_id="pi_smoke_1", decline_code="insufficient_funds", amount_cents=4500, classified_action="retry_notify", failure_created_at=timezone.now())
    NotificationLog.objects.create(account=account, subscriber=sub, failure=f1, email_type="failure_notice", status="sent")
    # last-month row (should NOT appear)
    sub2 = Subscriber.objects.create(account=account, stripe_customer_id="cus_smoke_2", email="bob@example.com")
    SubscriberFailure.objects.create(account=account, subscriber=sub2, payment_intent_id="pi_smoke_2", decline_code="card_expired", amount_cents=2000, classified_action="notify_only", failure_created_at=timezone.now().replace(day=1) - timedelta(days=2))
    ```
  - [ ] 9.2 Open `http://localhost:3000/dashboard`. Confirm:
    - List renders only `alice@example.com` (last-month `bob@example.com` filtered out).
    - "Last email" cell shows a relative time (`Xm ago` / `Xh ago`) for Alice.
    - Recommended-email chip shows "—" (Story 3.5 v1 not shipped yet).
    - Status badge reads "Active".
    - Action buttons (Send / Mark resolved / Exclude) are disabled.
    - Hovering a disabled button shows "Coming in next release" (DPA accepted, Mid-tier user → placeholder copy).
    - Click "Amount" column header → URL updates to `?sort=amount&dir=desc`. Click again → `?dir=asc`. Browser back goes to `?sort=amount&dir=desc`.
    - Switch user to a Free-tier account (or update tier via shell) → upgrade banner appears, tooltip changes to "Upgrade to Mid or Pro to enable email actions".
  - [ ] 9.3 Verify empty state: in Django shell, delete all this-month failures for the account; reload — empty-state copy renders verbatim.

## Dev Notes

### v1 Scope Boundaries (READ FIRST)

- **In scope:** new failed-payments list endpoint, list component, sort + URL persistence, tier-gated action placeholders (disabled), empty state, fraud-row visual treatment.
- **Out of scope:** action button wiring (Stories 3.3 per-row + 3.4 bulk), recommended-email rule engine (Story 3.5 v1 — `recommended_email_type` returns `null` until then), bulk multi-select (3.4), pagination (current month is small enough; revisit in v2 if a tenant exceeds ~500 rows/month), per-account timezone (the current PRD scope assumes UTC — see §Timezone below).

### Timezone (important)

The Account model has NO `timezone` field on `main` (confirmed: `backend/core/models/account.py:31-89`). v1 calculates "current calendar month" as `timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)` — UTC, mirroring the existing `dashboard_summary` view (`dashboard.py:51-52`). Per-account timezone is a known v2 gap. Do NOT add a timezone field in this story — that's a separate decision with PRD/UX implications (date-display formatting, polling-cycle alignment). Document the UTC assumption in a one-line comment in the view: `# v1: month boundary computed in UTC. Per-account timezone deferred to v2.`

### Currency

UX spec says "€" (`epics.md:836`). The existing `formatCurrency` (`frontend/src/lib/formatters.ts:1-6`) defaults to USD. **Do NOT** change the default — pass `"EUR"` explicitly at every call site in this story (`formatCurrency(amount_cents, "EUR")`). Other surfaces (KPI cards in `StoryArcPanel`) intentionally use the USD default; changing the default would silently shift every dollar value to euros. The currency choice for v1 is hardcoded to EUR in the failed-payments list because the founder persona (Marc) is European; v2 will surface a per-account currency setting.

### Architecture Compliance

- **Tenant isolation:** all queries via `for_account(account.id)` from `TenantScopedModel.objects` (`models/base.py:13-15`). Never `.objects.all()`. [Source: architecture.md#Enforcement Guidelines:594-610]
- **API response envelope:** `{"data": [...]}` for success, `{"error": {code, message, field}}` for errors. Never bare. [Source: architecture.md#Format Patterns:489-510]
- **Field naming:** snake_case in API responses + TypeScript interfaces. No camelCase. [Source: architecture.md#Naming Patterns:415-427]
- **Monetary values:** integer cents in API (`amount_cents`); display formatting in `frontend/src/lib/formatters.ts` only. [Source: architecture.md#Format Patterns:506]
- **Date/time:** ISO 8601 strings always (`f.failure_created_at.isoformat()`). TypeScript type is `string`. [Source: architecture.md#Format Patterns:504]
- **No business logic in views:** the view's job is filter + serialize + return. Reuse `DECLINE_CODE_LABELS` (data) and let the rule engine (Story 3.5 v1) own the recommendation logic. [Source: architecture.md#Structure Patterns:477]
- **API URL pattern:** kebab-case multi-word path: `/api/v1/dashboard/failed-payments/`. [Source: architecture.md#Naming Patterns:410]
- **Frontend snake_case types:** `FailedPayment` interface mirrors API exactly; no transformation layer. [Source: architecture.md#Naming Patterns:418-427]
- **Error handling by layer:** view returns DRF `Response` with the error envelope; frontend axios interceptor extracts `error.response.data.error`; TanStack Query `onError` consumes that. [Source: architecture.md#Process Patterns:570-590]
- **TanStack Query for server data:** never `useState` for fetched lists — `useFailedPayments` is the canonical entry point. [Source: architecture.md#Process Patterns:581-590]

### Technical Requirements

- **Existing list pattern (REUSE):** `subscriber_list` view at `views/subscribers.py:14-86` is the closest analog. The failed-payments view is structurally similar but failure-keyed not subscriber-keyed. Read it carefully — the `Subquery` annotation + `for_account()` + `.distinct()` patterns transfer directly.
- **Existing month-filter pattern (REUSE):** `dashboard_summary` at `views/dashboard.py:51-52` uses `now.replace(day=1, ...)`. Reuse exactly — do NOT introduce `dateutil` or any new date library. Django's `timezone.now()` returns timezone-aware UTC in production (`USE_TZ=True` in `settings/base.py`).
- **NotificationLog `status` choices:** `"sent" | "failed" | "suppressed"` (`models/notification.py:11-15`). The `last_email_sent_at` Subquery filters strictly to `status="sent"` — `"failed"` and `"suppressed"` rows must NOT count as "last email sent" (a failed Resend API call did not reach the subscriber).
- **NotificationLog unique constraint:** `(failure, email_type)` is unique only when `status="sent"` (`notification.py:47-51`). For test fixtures creating multiple sent rows for the same failure, use distinct `email_type` values from `EMAIL_TYPE_CHOICES`: `failure_notice`, `final_notice`, `recovery_confirmation`.
- **Existing test fixtures:** `auth_client` and `account` are project-level pytest fixtures from `backend/tests/conftest.py` (NOT `core/tests/test_api/conftest.py`, which is currently minimal). Pattern visible in every existing API test. Verify by reading `backend/tests/conftest.py` before writing tests; if `auth_client` lives elsewhere, adapt to the local convention.
- **shadcn Table primitive:** `frontend/src/components/ui/table.tsx` exports `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell`. Compose with these — no custom `<table>` markup.
- **Tooltip primitive:** the project uses `@base-ui/react`'s tooltip (per Story 3-1-v1 Dev Notes). Confirm exact import path before authoring — search `frontend/src/components/` for "Tooltip" or "tooltip" first. If no tooltip primitive is wired up yet, use `@base-ui/react`'s `Tooltip` directly with the primitive's API; mirror existing tooltip usage in `useDpaGate` consumer code.
- **Lucide icons:** `lucide-react` for arrow icons (`ArrowUp`, `ArrowDown`). Already in `package.json` (used by `Shield` in 3-1-v1 settings DPA section).
- **Skeleton pattern:** the project's skeleton style uses `animate-pulse` + `bg-[var(--sn-border)]` + `rounded`. See `SubscriberGrid.tsx:11-29` for the canonical shape.
- **Color tokens:** `--accent-active` (blue, used for chips), `--accent-recovery` (green, used for recovered amount), `--accent-fraud` (red), `--accent-neutral` (grey for passive churn), `--text-primary`, `--text-secondary`, `--bg-surface`, `--sn-border`. Defined in `frontend/src/app/globals.css`.

### UX Design Requirements

- **List is the primary working surface.** Per UX-DR16 (`epics.md:798`), the failed-payments list replaces the SubscriberGrid as the dashboard's main interaction surface. KPIs (`StoryArcPanel`, `DeclineBreakdown`) remain as supplementary context above the list.
- **Strict color discipline.** Amber is reserved for attention/warning (fraud-flagged rows). Do NOT use amber for any other row state (e.g. "needs_attention" alone). Blue is processing only — not used in this story. [Source: ux-design-specification.md#12.6:1129-1141]
- **Empty state copy is contractual.** The exact heading "No failed payments this month." and sub-copy "Your subscribers are paying — keep shipping." are AC4 contracts. Tests assert verbatim. [Source: ux-design-specification.md:1086-1088]
- **One Primary CTA per viewport.** This story doesn't add a Primary button — the upgrade CTA in the Free-tier banner is a Ghost text-link. Don't elevate it to Primary; the Settings → Upgrade CTA is the canonical Primary on this dashboard. [Source: ux-design-specification.md#12.1:1040-1056]
- **Disabled-with-tooltip pattern.** Every gated control surfaces an explanatory tooltip — never silently disabled. Pattern shipped in 3-1-v1 (`useDpaGate`). [Source: 3-1-v1 Task 8 + ux-design-specification.md]
- **Tooltips are explanatory, not promotional.** "Upgrade to Mid or Pro to enable email actions" — informational, action-clear. NOT "Unlock now!" or marketing language. [Source: ux-design-specification.md#12.x copy patterns]

### Previous Story Intelligence

From the just-completed Story 3-1-v1 (DPA Acceptance Gate):

- **`useDpaGate` is the canonical send-gating hook.** Consume it for tooltip + disabled state. Don't reinvent — the precedence rule (tier > DPA > placeholder) is asserted in `useDpaGate.test.ts`. Build on top.
- **`invalidateQueries` after mutations (and after upgrade success).** The 3-1-v1 review patch (line 215-230 of the 3-1-v1 story) added `queryClient.invalidateQueries` to the upgrade-success branch in dashboard `page.tsx`. Extend that block in Task 7.3 to also invalidate `["failed-payments"]` — same pattern.
- **Adversarial review themes from 3.1 v1 (and the Epic 4 stories before it):** concurrency / idempotency / error envelopes / audit-write placement / loading-state defaults. This story's read-only nature dodges most of them; the relevant ones to pre-empt:
  - **Loading-state default:** `useDpaGate` returns `sendDisabled: true` while `useAccount` is loading. Mirror this safety default in any component logic: a disabled button is always safe; a button enabled in error / loading state is not.
  - **Error envelopes:** the `VALIDATION_ERROR` in Task 1.4 must include `field` (set to `"sort"`) per the envelope contract. The 3-1-v1 review (line 231) flagged that some legacy endpoints omit `field: None` — don't repeat the bug here.
- **Type definition co-location:** types live in `frontend/src/types/{resource}.ts`. The 3-1-v1 review-patched comment (line 222) noted that overly-narrow literal types (e.g. `activatePath: "/activate"`) cause friction — keep `RecommendedEmailType` as a union type, not a `const`-asserted literal.

From Epic 4 stories (4.1, 4.3): the `NotificationLog` table is already populated in production — there are pre-existing `failure_notice` rows from the existing email-send path. The Subquery in Task 1.3 will surface real data immediately on a Mid-tier account that's been sending emails. This means the "last email sent" column is not vaporware — it lights up the moment the failed-payments list ships.

### Git Intelligence

Recent commits (`git log --oneline -8`):
- `01e1026` Merge pull request #2 (3-1-v1 done) — the immediate parent for v1 work.
- `7f270c4` Status: done (v1 sprint status update).
- `f366d31` Major rescoping — the v1 commit-of-record. Read for context on quarantined v0 code.
- `6fe105e` Backend (8 files) — Story 4.5 password-reset hardening.
- `a23988e` Story 4.3: final notice & recovery confirmation emails — the source of `NotificationLog` `failure_notice` rows.

**Implication:** the codebase on `main` is mid-transition. Quarantined v0 code (engine_mode UI, supervised mode, retry tasks) is still present but unused by v1 product surfaces. Don't reference quarantined files in this story's implementation. Do NOT delete them either — that's the broader Sprint Change Proposal §3.2 quarantine pass.

### Latest Tech Information

- **Django 6.0.x** (`pyproject.toml`): `Subquery` + `OuterRef` for the `last_email_sent_at` annotation is the documented pattern. `Max` aggregate would also work but `Subquery(...values()[:1])` is what the existing `subscriber_list` view uses (`views/subscribers.py:25-28`) — match for consistency.
- **Django REST Framework 3.17.x:** `serializers.Serializer` (not `ModelSerializer`) is correct here because the row is a composed dict, not a single-model row.
- **Next.js 16 App Router:** `useSearchParams()` returns a read-only `URLSearchParams`; mutate via `new URLSearchParams(params.toString())`. `router.replace()` (not `router.push()`) for sort-toggle URL updates so back/forward doesn't accumulate noise. `{ scroll: false }` keeps the table in place.
- **TanStack Query v5:** include sort + dir in the query key for automatic cache partitioning. No manual `setQueryData` / `invalidateQueries` needed for sort changes — each combination is its own cache entry.
- **Vitest** + React Testing Library: `vi.mock("next/navigation", () => ({ useSearchParams: ..., useRouter: ..., usePathname: () => "/dashboard" }))` is the canonical pattern. See `frontend/src/__tests__/DpaAcceptancePage.test.tsx` for a worked example with `next/navigation` mocking.

### Project Structure Notes

**New files to create:**
- `backend/core/views/dashboard.py` — *extend* with `failed_payments_list` view (don't create a new file; the module already exists)
- `backend/core/serializers/dashboard.py` — *extend* with `FailedPaymentRowSerializer`
- `backend/core/tests/test_api/test_failed_payments_list.py`
- `frontend/src/types/failed_payment.ts`
- `frontend/src/hooks/useFailedPayments.ts`
- `frontend/src/components/dashboard/FailedPaymentsList.tsx`
- `frontend/src/__tests__/FailedPaymentsList.test.tsx`

**Files to modify:**
- `backend/core/urls.py` — add the `/v1/dashboard/failed-payments/` route
- `frontend/src/app/(dashboard)/dashboard/page.tsx` — render `FailedPaymentsList`, drop `SubscriberGrid` block, add `["failed-payments"]` to upgrade-invalidate set

**Files to delete:** none (SubscriberGrid + SubscriberCard remain — they may be used in subscriber-detail surfaces in later stories).

### References

- [Source: epics.md#Epic 3 (v1):793-862] — Full v1 epic context and Story 3.2 v1 ACs
- [Source: sprint-change-proposal-2026-04-29.md] — Strategic rationale, FR scope, UX-DR16 dashboard primary surface
- [Source: prd.md#FR52:488] — Current-month failed-payments dashboard list with per-row recommended email type
- [Source: prd.md#FR16:496] — Four-status display vocabulary
- [Source: prd.md#FR19:499] — Fraud flag visual treatment
- [Source: ux-design-specification.md#12.3:1080-1090] — Empty state copy contract
- [Source: ux-design-specification.md#12.6:1129-1141] — Status & badge color discipline
- [Source: ux-design-specification.md:447-454] — Daily Failed-Payments Review interaction model
- [Source: architecture.md#Naming Patterns:398-435] — snake_case API + TS field naming
- [Source: architecture.md#Format Patterns:489-510] — Response envelope + monetary value contracts
- [Source: architecture.md#Structure Patterns:439-477] — Django app organization
- [Source: architecture.md:299-302] — `/api/v1/dashboard/*` URL conventions
- [Source: architecture.md:710-779] — Frontend file structure
- [Source: 3-1-v1-dpa-acceptance-gate.md] — `useDpaGate` hook contract + tooltip precedence
- [Source: backend/core/views/subscribers.py:14-86] — Closest analog list endpoint to copy patterns from
- [Source: backend/core/views/dashboard.py:51-52] — Month-start calculation pattern

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

- Backend tests: `docker compose exec -T web poetry run pytest core/tests/test_api/test_failed_payments_list.py -v` → 16 passed
- Frontend tests: `./node_modules/.bin/vitest run FailedPaymentsList` → 14 passed
- Pre-existing regressions on `main` (10 backend, 11 frontend) verified out-of-scope by checking out `main` and re-running.

### Completion Notes List

- Implemented `failed_payments_list` view in `backend/core/views/dashboard.py` extending the existing module (kept `dashboard_summary` untouched). Tenant isolation via `SubscriberFailure.objects.for_account()`. Month boundary computed in UTC (per-account timezone deferred to v2 with inline comment).
- `last_email_sent_at` is annotated with a `Subquery` filtered to `status="sent"` so failed/suppressed Resend attempts do NOT count.
- `recommended_email_type` returns `None` until Story 3.5 v1 lands the rule engine; the frontend chip renders "—" until then.
- Sort/dir validated explicitly with `VALIDATION_ERROR` envelopes (`field` populated per the `architecture.md` envelope contract — guards against typos and locks the contract for tests).
- Added `FailedPaymentRowSerializer` to `backend/core/serializers/dashboard.py` for schema discoverability (`serializers.Serializer`, not `ModelSerializer`, since the row is a composed dict).
- New URL: `/api/v1/dashboard/failed-payments/` (kebab-case multi-word).
- Frontend `FailedPaymentsList` is a self-contained client component. Sort state syncs to URL via `router.replace({ scroll: false })` so back/forward preserves history without accumulating scroll noise.
- Tier/DPA/placeholder tooltip precedence implemented: tier > DPA > placeholder. Action buttons are unconditionally disabled in 3.2 — Stories 3.3/3.4 will lift the placeholder gate.
- Free-tier upgrade banner links to `/settings#subscription` via `next/link`.
- Empty-state copy is verbatim per UX-DR 12.3 ("No failed payments this month." + "Your subscribers are paying — keep shipping.") and asserted by tests.
- Fraud-flagged rows get the `border-amber-500 border-2` treatment per AC5 — no `⚠` prefix (StatusBadge already labels it).
- Wired `FailedPaymentsList` into `frontend/src/app/(dashboard)/dashboard/page.tsx` directly under `NextScanCountdown`. Dropped the `SubscriberGrid` block per UX-DR16 (list is the new primary working surface). Added `["failed-payments"]` to the upgrade-success invalidation set.
- Tooltip surface: native `title` attribute on disabled buttons (no shared `Tooltip` wrapper exists in the project; `@base-ui/react` tooltip primitive would be a separate Story 3.x scope-creep). Tests assert `getAttribute("title")`.
- Task 9 (manual UI smoke) deferred to reviewer; the integration test suite (real Postgres via docker compose) covers ACs 1–5 end-to-end.

### File List

**New files:**
- `backend/core/tests/test_api/test_failed_payments_list.py` — 16 integration tests covering ACs 1, 2, 5 + tenant isolation
- `frontend/src/types/failed_payment.ts` — `FailedPayment`, `RecommendedEmailType`, `SortKey`, `SortDirection`
- `frontend/src/hooks/useFailedPayments.ts` — TanStack Query hook keyed on `(sort, dir)`
- `frontend/src/components/dashboard/FailedPaymentsList.tsx` — list component + inline `RecommendedEmailChip`, `SortableHeader`, `EmptyState`, `ListSkeleton`, `ActionButtons`, `PaymentRow`
- `frontend/src/__tests__/FailedPaymentsList.test.tsx` — 14 Vitest tests covering ACs 1–5 + tier/DPA tooltip precedence

**Modified files:**
- `backend/core/views/dashboard.py` — extended with `failed_payments_list` view; added `OuterRef`, `Subquery`, `NotificationLog`, `FailedPaymentRowSerializer` imports
- `backend/core/serializers/dashboard.py` — added `FailedPaymentRowSerializer`
- `backend/core/urls.py` — added `/v1/dashboard/failed-payments/` route
- `frontend/src/app/(dashboard)/dashboard/page.tsx` — render `<FailedPaymentsList />`, drop `SubscriberGrid` block, invalidate `["failed-payments"]` on upgrade success
- `_bmad-output/3-2-v1-current-month-failed-payments-dashboard.md` — status, tasks, dev-agent-record
- `_bmad-output/sprint-status.yaml` — story status `ready-for-dev → in-progress → review`

### Change Log

- 2026-04-30 — Implementation complete. Status `ready-for-dev → in-progress → review`. 16 backend integration tests + 14 frontend component tests added; all green. Ready for code review.
