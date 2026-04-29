---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories]
inputDocuments:
  - _bmad-output/prd.md
  - _bmad-output/architecture.md
  - _bmad-output/ux-design-specification.md
---

# SafeNet - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for SafeNet, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: A new user can connect their Stripe account to SafeNet via OAuth without handling API keys
FR2: SafeNet can perform a retroactive 90-day payment failure scan immediately after Stripe Connect authorization
FR3: A client must acknowledge and sign a Data Processing Agreement before the recovery engine is activated
FR4: A client can choose between Supervised mode and Autopilot mode as their retry authorization model
FR5: A client can switch between Supervised and Autopilot mode at any time after initial setup
FR6: SafeNet can detect new failed payment events from a connected Stripe account on an hourly polling cycle
FR7: SafeNet can classify each failed payment by its Stripe decline code
FR8: SafeNet can display a breakdown of all detected failures by decline code category
FR9: SafeNet can calculate and display an estimated recoverable revenue figure based on detected failures
FR10: SafeNet can apply distinct recovery rules to each decline code category (retry-only, notify-only, retry+notify, no-action)
FR11: SafeNet can schedule `insufficient_funds` retries within a 24-hour window after the 1st or 15th of the month
FR12: SafeNet can enforce a maximum retry count per failure by decline code category: `insufficient_funds` (3 retries), `do_not_honor` / `generic_decline` (2 retries), `card_velocity_exceeded` (1 retry), `card_expired` (0 retries — notify only), all other codes (1 retry unless overridden by rule engine)
FR13: SafeNet can detect EU/UK payment contexts (identified via Stripe payment method country or customer billing address country) and route them to notify-only, blocking automated retries
FR14: In Supervised mode, SafeNet queues pending actions for explicit client approval before execution
FR15: In Autopilot mode, SafeNet executes recovery actions automatically per the rule engine without client intervention
FR16: SafeNet assigns and displays one of four statuses to each end-customer with a failed payment: Active, Recovered, Passive Churn, Fraud Flagged
FR17: SafeNet can transition a customer from Active to Recovered when a retry succeeds
FR18: SafeNet can transition a customer to Passive Churn when the retry cap is exhausted without recovery
FR19: SafeNet immediately flags a customer as Fraud Flagged and stops all actions when a fraud decline code is detected
FR20: A client can view the payment history and current status for any individual end-customer
FR21: A client can manually resolve a Fraud Flagged status and record a resolution reason
FR22: SafeNet can send a branded email notification to an end-customer when their payment fails
FR23: A client can select the notification tone from three presets (Professional / Friendly / Minimal)
FR24: SafeNet can send a final notice email to an end-customer on the last retry attempt, before graduating them to Passive Churn
FR25: SafeNet can send a payment recovery confirmation email to an end-customer when a retry succeeds
FR26: Every notification sent to an end-customer includes a functional opt-out mechanism
FR27: SafeNet suppresses all future notifications for an end-customer who has opted out via a SafeNet notification link. All SafeNet notifications are classified as transactional messages (contractual necessity) — a standard marketing opt-out from the client's own communications does not suppress SafeNet notifications.
FR28: Mid-tier clients' notifications are sent from a SafeNet-managed shared sending domain with the client's brand name in the From field
FR29: A client's dashboard is populated with retroactive scan data on first login — no empty state
FR30: A client can view failures segmented by decline code, customer status, and estimated recoverable revenue
FR31: A client can view recovery analytics showing recovered payments, successful retry attempts, and notifications that drove card updates
FR32: A client can view a month-over-month comparison of failure rate, recovery rate, revenue protected, and Passive Churn count
FR33: A client can opt in to receive a weekly digest email summarizing recovery activity, active retries, and new Passive Churn flags — disabled by default, togglable from account settings
FR34: SafeNet sends a triggered onboarding email to the client when their first scan completes
FR35: SafeNet provides full Mid-tier access to any new account for 30 days without requiring a payment method
FR36: SafeNet downgrades a non-converting account to the Free tier after the 30-day trial, reducing polling to twice-monthly
FR37: A Free-tier client can see the time remaining until their next payment scan in the dashboard
FR38: SafeNet sends a monthly email to active Mid-tier clients showing recovered revenue versus subscription cost
FR39: A client can upgrade from Free to Mid tier from a single CTA anchored to the estimated recoverable revenue figure
FR40: The SafeNet operator can view all scheduled retries across all accounts before they fire
FR41: The SafeNet operator can cancel a scheduled retry and record a reason in the audit log
FR42: The SafeNet operator can manually advance a customer's status and record the reason
FR43: SafeNet records every engine action in an append-only audit log with timestamp, actor, and outcome
FR44: The SafeNet operator can view the full audit log for any customer or account
FR45: The operator console is accessible only to authenticated SafeNet operators and is not exposed to clients
FR46: SafeNet can detect when an end-customer's Stripe subscription moves to a non-recoverable state (`cancelled`, `unpaid`, `paused`) or is flagged as `cancel_at_period_end`, and automatically stops all recovery actions, graduating the customer to Passive Churn with the specific reason recorded
FR47: SafeNet can detect when an end-customer updates their payment method and queue an immediate retry for their most recent Active-status failure, independent of the payday-aware schedule
FR48: Each client account supports exactly one user at MVP — multi-user access and team invitations are not available

### NonFunctional Requirements

NFR-S1: All Stripe OAuth tokens are encrypted at rest using AES-256; the encryption key is stored exclusively in environment secrets and never in the database
NFR-S2: All data in transit is encrypted using TLS 1.2 minimum
NFR-S3: SafeNet stores zero raw cardholder data — only Stripe event metadata (payment intent IDs, decline codes, timestamps, retry outcomes)
NFR-S4: All operator console access requires authentication; the console is not accessible to client accounts
NFR-S5: All data queries are scoped by tenant identifier at the application layer — no cross-tenant data access is possible through the application
NFR-S6: Any confirmed security incident triggers a production hotfix within 4 hours of confirmation — no exceptions, no scheduled release queue
NFR-R1: The hourly polling job executes every 60 minutes (±5 minutes tolerance); a missed cycle triggers an operator alert within 90 minutes
NFR-R2: Scheduled retries fire within their designated time window with ≤15 minutes variance
NFR-R3: Every engine action either succeeds or is logged as failed with a reason — zero silent failures permitted
NFR-R4: System uptime target: ≥99.5% measured monthly
NFR-R5: The job queue implements dead-letter handling — failed jobs are captured, logged, and surfaced for operator review rather than silently dropped
NFR-P1: Dashboard loads within 3 seconds for accounts with up to 500 end-customers
NFR-P2: The 90-day retroactive scan runs as a background job and does not block the dashboard UI at any point
NFR-P3: First scan data is visible in the dashboard within 5 minutes of Stripe Connect authorization
NFR-P4: Polling retries automatically on rate limit errors without hard failure — no polling cycle is abandoned due to temporary API throttling
NFR-SC1: MVP architecture supports up to 100 connected client accounts without infrastructure changes
NFR-SC2: The polling job handles up to 10,000 payment events per client account per polling cycle
NFR-SC3: The data model supports multi-user account expansion without schema migration of existing account or user records
NFR-D1: Payment event metadata is retained for 24 months from the event date, then automatically purged
NFR-D2: Audit logs are retained for 36 months — longer than event data to satisfy compliance review windows
NFR-D3: End-customer email addresses are purged within 30 days of a customer reaching Passive Churn status, unless the client account remains active and requests retention for win-back purposes

### Additional Requirements

- **Monorepo project structure:** Single git repo with `backend/` (Django + Celery) and `frontend/` (Next.js) subdirectories, deployed as separate Railway services
- **Starter template — Backend:** `django-admin startproject` with `core` app; pip-install: `django==6.0.3 djangorestframework==3.17.1 celery==5.6.3 redis django-environ psycopg2-binary cryptography djangorestframework-simplejwt django-fsm django-cors-headers django-redis drf-spectacular sentry-sdk`
- **Starter template — Frontend:** `create-next-app` with TypeScript + Tailwind + App Router + ESLint + `src/` dir; install: `shadcn/ui`, `@tanstack/react-query@5`, `zustand`, `axios`, `@sentry/nextjs`
- **Docker Compose (6 services):** `db` (PostgreSQL), `redis`, `web` (Django), `worker` (Celery worker), `beat` (Celery beat scheduler), `frontend` (Next.js) — mirrors production; one-command local environment
- **TenantScopedModel + TenantManager:** Abstract base class with required `account` FK; custom manager makes `Model.objects.all()` require `account_id` scoping; `unscoped()` manager available only in admin/operator context
- **JWT authentication:** `djangorestframework-simplejwt` — 15-min access token, 7-day refresh token; Next.js middleware handles transparent refresh; stateless (no server-side sessions)
- **Stripe token encryption:** `cryptography.fernet` (AES-128-CBC with HMAC); `FERNET_KEY` loaded exclusively from Railway environment secrets; only `StripeConnection` model uses encrypt/decrypt helpers
- **Decline-code rule engine:** Data-driven Python dict config (`DECLINE_RULES`) in `core/engine/rules.py`; 30+ codes mapped to `{action, retry_cap, payday_aware, geo_block}`; unknown codes fall to conservative `_default`; zero DB dependency — fully testable with pytest
- **4-state FSM:** `django-fsm` for `Subscriber` model; transitions: Active → Recovered / Passive Churn / Fraud Flagged; `TransitionNotAllowed` raised on invalid transitions; post-transition signal writes audit trail automatically
- **Append-only audit log:** Every engine action, status change, and operator intervention written via `write_audit_event()` helper; never inline; append-only (no update/delete paths in application layer)
- **Redis caching:** Django cache backend (`django-redis`); dashboard summary endpoint cached 5-min TTL; invalidated on any engine action for that account; individual subscriber data never cached
- **API design:** REST via DRF; resource-oriented; all fields snake_case in both Django responses AND TypeScript types (no transformation layer); monetary values as integer cents (`amount_cents`); dates as ISO 8601 strings; response envelope always `{data: ...}` or `{error: ...}`
- **OpenAPI docs:** `drf-spectacular` generating OpenAPI 3.0 at `/api/schema/` (internal); contract between backend and frontend during development
- **Operator console isolation:** Django admin mounted at `/ops-console/` (not `/admin/`); only `is_staff=True` users; client accounts always `is_staff=False`; separate URL routing from client-facing API
- **CI/CD:** GitHub Actions — `test.yml` (pytest + ESLint on every PR), `deploy.yml` (Railway deploy on merge to main)
- **Error monitoring:** Sentry — `sentry-sdk` on backend, Sentry Next.js SDK on frontend; free tier sufficient for MVP
- **Celery beat single-instance constraint:** `celery beat` must run as a single Railway instance — multiple instances would double-fire retries; enforced via Railway service config
- **Frontend state management:** TanStack Query (React Query v5) for all server state; Zustand for UI-only client state (active sheet subscriber ID, batch selection, theme, mode state); axios with JWT interceptor + 401 auto-refresh
- **Data retention automation:** Automated purge jobs for 24-month event metadata and 30-day post-Passive-Churn email purge; 36-month audit log retention enforced

### UX Design Requirements

UX-DR1: Implement Story Arc 3-column layout (Detected → In Progress → Recovered) as the primary dashboard — CSS Grid with 1px hairline dividers on `#E2E5EF` background; top navigation (horizontal) replaces sidebar for founder-facing screens
UX-DR2: Build `RecoveryHeroCard` custom component — 56px Inter 700 green hero amount, "Recovered this month" eyebrow, supporting retry count + net benefit line; states: Default / Free tier (estimated recoverable + trial CTA) / Loading skeleton; `aria-label` with full context
UX-DR3: Build `StoryArcPanel` custom component — 3-column CSS Grid, each column has step indicator + title + hero metric + supporting KPIs + item list; Column 1: neutral, Column 2: blue + estimated recoverable + recovery rate, Column 3: green tint; states: Default / Scan loading skeleton / Zero state
UX-DR4: Build `AttentionBar` component — conditionally rendered amber strip below topbar; amber warning icon + "N items need your attention" + "Review before next engine cycle in Xm"; named action pills (clickable chips); states: Visible / Hidden / Urgent (fraud flag — deeper amber); `role="alert"` with `aria-live="polite"`
UX-DR5: Build `EngineStatusIndicator` component — animated pulse dot (blue=active, grey=paused, amber=error); "Autopilot active" / "Supervised" / "Paused" text + "Last scan Xm ago · next in Ym"; topbar right-anchored on all authenticated screens; `aria-live="polite"` on status change
UX-DR6: Build `WorkspaceIdentity` component — SafeNet wordmark + vertical divider + 2-letter SaaS monogram avatar + SaaS name (bold 13px) + "Marc's workspace" sub-label; left-anchored topbar; always visible on authenticated screens
UX-DR7: Build `DeclineCodeExplainer` component — maps Stripe codes to plain-language human label + single-sentence popover explanation; code never shown in UI; used in subscriber list, detail panel, StoryArcPanel, review queue
UX-DR8: Build `BatchActionToolbar` component — selection count + "Apply recommended actions" primary CTA + "Exclude from automation" ghost/destructive + deselect all link; slides up from bottom on row selection; sticky within queue viewport; `role="toolbar"` with keyboard nav
UX-DR9: Build `SubscriberCard` component — name (bold) + amount (right-aligned) + email/tier sub-label + plain-language decline reason + status badge; states: Default / Hover (border darkens) / Attention (amber border + ⚠ prefix) / Recovered (green amount); attention-state cards always render first
UX-DR10: Extend shadcn/ui `Badge` with 4 SafeNet status variants: Recovered (green / `--accent-recovery`), Active (blue / `--accent-active`), Fraud Flagged (red / `--accent-fraud`), Passive Churn (grey / `--accent-neutral`); text label always paired with colour — never colour-only communication
UX-DR11: Implement full-screen retroactive scan experience — no partial data during scan; animated progress + "Scanning your last 90 days of payment activity"; single-reveal dashboard populate (not incremental); hero metric appears first; post-scan CTA anchored below estimated recoverable figure
UX-DR12: Implement design token system — CSS custom properties for all 12 semantic tokens in both light and dark variants; wire to shadcn/ui theme switching; extend Tailwind config with SafeNet semantic token aliases; Inter variable font (self-hosted or CDN); `font-variant-numeric: tabular-nums` for all monetary values
UX-DR13: Implement WCAG AA accessibility throughout — all status badges have `aria-label` with full status text; KPI numbers have `aria-label` with currency + context; all interactive elements have visible focus rings using `--accent-active`; scan animation and reveals respect `prefers-reduced-motion`; no text below 11px; colour-blind safe (text label always paired with colour)
UX-DR14: Implement responsive layout — desktop (≥1280px): full layout; laptop (1024–1279px): condensed 200px sidebar equiv; tablet (768–1023px): sidebar collapses to icon rail; mobile (<768px): sidebar hidden, top nav, read-only optimised; complex actions (batch review, DPA signing) are desktop-only
UX-DR15: Implement DPA as a distinct full-page formal screen (not a checkbox) — presented between trial activation and mode selection; explicit sign/accept action; documents what SafeNet processes, on whose behalf, for what purpose; hard gate before engine activation
UX-DR16: Implement Supervised mode review queue — list with name + plain-language decline reason + recommended action (pre-selected per decline code) + amount at risk; multi-select checkboxes; batch toolbar appears on selection; exclusion requires confirmation dialog; zero-state: "Nothing needs your eyes right now."
UX-DR17: Implement live notification preview in tone selector settings — Marc sees exactly what subscribers will receive (with his brand name) in real time as tone preset is selected (Professional / Friendly / Minimal); preview updates instantly on preset change
UX-DR18: Implement affirming zero/empty states for all screens — "You're all clear." (Dashboard / no failures), "Nothing needs your eyes right now." (Review queue), "Your first recovery is coming." (Recovered / no recoveries yet), "Connect Stripe to activate SafeNet." (Settings / no Stripe)

### FR Coverage Map

| FR | Epic | Area |
|----|------|------|
| FR1 | Epic 2 | Stripe Connect OAuth |
| FR2 | Epic 2 | 90-day retroactive scan |
| FR3 | Epic 3 | DPA gate before engine activation |
| FR4 | Epic 3 | Supervised / Autopilot mode selection |
| FR5 | Epic 3 | Mode switch at any time |
| FR6 | Epic 2 | Hourly polling failure detection |
| FR7 | Epic 2 | Decline code classification |
| FR8 | Epic 2 | Failure breakdown by decline code |
| FR9 | Epic 2 | Estimated recoverable revenue KPI |
| FR10 | Epic 3 | Code-aware recovery rule application |
| FR11 | Epic 3 | Payday-aware retry calendar |
| FR12 | Epic 3 | Per-code retry caps |
| FR13 | Epic 3 | EU/UK geo-aware compliance layer |
| FR14 | Epic 3 | Supervised mode pending action queue |
| FR15 | Epic 3 | Autopilot automatic execution |
| FR16 | Epic 3 | 4-status customer state machine |
| FR17 | Epic 3 | Active → Recovered transition |
| FR18 | Epic 3 | Active → Passive Churn transition |
| FR19 | Epic 3 | Fraud flag + action stop |
| FR20 | Epic 5 | Individual subscriber detail view |
| FR21 | Epic 5 | Manual fraud flag resolution |
| FR22 | Epic 4 | Branded failure notification email |
| FR23 | Epic 4 | Tone selector (3 presets) |
| FR24 | Epic 4 | Final notice email |
| FR25 | Epic 4 | Recovery confirmation email |
| FR26 | Epic 4 | Opt-out mechanism in every notification |
| FR27 | Epic 4 | Opt-out suppression logic |
| FR28 | Epic 4 | Shared domain sending (SafeNet-managed) |
| FR29 | Epic 2 | First-login populated dashboard |
| FR30 | Epic 2 | Failure breakdown / dashboard view |
| FR31 | Epic 5 | Recovery analytics section |
| FR32 | Epic 5 | Month-over-month comparison |
| FR33 | Epic 5 | Weekly digest email (opt-in) |
| FR34 | Epic 2 | Triggered onboarding email post-scan |
| FR35 | Epic 2 | 30-day Mid-tier trial (no card required) |
| FR36 | Epic 2 | Post-trial degradation to Free |
| FR37 | Epic 2 | "Next scan in X days" indicator |
| FR38 | Epic 5 | Monthly "SafeNet saved you" billing email |
| FR39 | Epic 2 | Upgrade CTA anchored to recoverable revenue |
| FR40 | Epic 6 | Operator: view all scheduled retries |
| FR41 | Epic 6 | Operator: cancel retry + audit note |
| FR42 | Epic 6 | Operator: manual status advancement |
| FR43 | Epic 6 | Append-only audit log (every action) |
| FR44 | Epic 6 | Operator: full audit log view |
| FR45 | Epic 6 | Operator console: operator-only access |
| FR46 | Epic 3 | Subscription cancellation → Passive Churn |
| FR47 | Epic 3 | Card-update triggered immediate retry |
| FR48 | Epic 2 | Single-owner account (no team access at MVP) |

## Epic List

### Epic 1: Project Foundation & Deployable Skeleton
A working, fully deployable project skeleton with security patterns, tenant isolation, and the core engine config in place — enabling all feature epics to build on a solid, consistent foundation.
**FRs covered:** *(foundation — no direct FRs; satisfies NFR-S1, NFR-S2, NFR-S3, NFR-S5, NFR-SC3)*

### Epic 2: Founder Onboarding & Free Tier Dashboard
A founder can connect their Stripe account, immediately see a populated 90-day failure landscape (never an empty state), understand their recoverable revenue, manage their account, and upgrade to Mid tier.
**FRs covered:** FR1, FR2, FR6, FR7, FR8, FR9, FR29, FR30, FR34, FR35, FR36, FR37, FR39, FR48

### Epic 3 (v0): Recovery Engine, Compliance & Customer Status Management — QUARANTINED 2026-04-29
Preserved on `archive/v0-recovery-engine` branch. Not in v1 product. See `_bmad-output/sprint-change-proposal-2026-04-29.md`.
**FRs covered (v0):** FR3, FR4, FR5, FR10, FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR46, FR47

### Epic 3 (v1): DPA Gate, Failed-Payments Dashboard & Email Actions
A Mid-tier client signs the DPA, then opens their dashboard to see all current-month failed payments with a recommended dunning email per row. They click to send (single or batch), choose a different email type if they prefer, or mark a failure as resolved. Status transitions are polling-detected and Marc-initiated.
**FRs covered:** FR3, FR10, FR16, FR17, FR18, FR19, FR52, FR53, FR54, FR55

### Epic 4: End-Customer Notification System
Mid-tier clients' subscribers receive compliant, branded email notifications (with tone selection, opt-out mechanism, and recovery confirmation) — making the end-customer experience indistinguishable from a well-run in-house billing operation.
**FRs covered:** FR22, FR23, FR24, FR25, FR26, FR27, FR28, FR51, FR56

### Epic 5: Subscriber Detail, Analytics & Retention Emails
A client can drill into any individual subscriber's full payment history, review recovery analytics and month-over-month trends, manage fraud flag resolutions, and receive automated emails that prove SafeNet's value (weekly digest + monthly "SafeNet saved you" email).
**FRs covered:** FR20, FR21, FR31, FR32, FR33, FR38

### Epic 6: Operator Administration Console
The SafeNet operator can monitor all scheduled retries across all client accounts, intervene when needed (cancel retries, advance customer status), and review the full append-only audit trail — with strict access control ensuring no client can reach operator capabilities.
**FRs covered:** FR40, FR41, FR42, FR43, FR44, FR45

---

## Epic 1: Project Foundation & Deployable Skeleton

A working, fully deployable project skeleton with security patterns, tenant isolation, and the core engine config in place — enabling all feature epics to build on a solid, consistent foundation.

**Satisfies:** NFR-S1, NFR-S2, NFR-S3, NFR-S5, NFR-SC3; Architecture requirements; UX-DR12

### Story 1.1: Monorepo Initialization, Docker Compose & CI/CD Pipeline

As a developer,
I want a monorepo with a one-command local dev environment and automated CI/CD,
So that both services can be built, tested, and deployed consistently from day one.

**Acceptance Criteria:**

**Given** a fresh clone of the repository
**When** I run `docker compose up`
**Then** all 6 services start successfully: `db` (PostgreSQL), `redis`, `web` (Django dev server on :8000), `worker` (Celery worker), `beat` (Celery beat scheduler), `frontend` (Next.js on :3000)
**And** each service can communicate with its dependencies (Django connects to PostgreSQL and Redis; Celery worker connects to Redis)

**Given** a pull request is opened on GitHub
**When** the `test.yml` GitHub Actions workflow runs
**Then** it executes `pytest` against the Django backend and `eslint` against the Next.js frontend
**And** the workflow fails if any test or lint check fails, blocking merge

**Given** a commit is merged to `main`
**When** the `deploy.yml` workflow runs
**Then** the backend and frontend are deployed to their respective Railway services
**And** the deploy fails with a visible error (not silently) if Railway rejects the deployment

**Given** the monorepo structure
**When** I inspect the root directory
**Then** it contains `backend/` (Django project), `frontend/` (Next.js project), `docker-compose.yml`, and `.github/workflows/`
**And** `celery beat` is configured to run as exactly one Railway instance — multiple instances are prevented to avoid double-firing retries

---

### Story 1.2: Django Core: Tenant Isolation, JWT Auth & Stripe Token Encryption

As a developer,
I want the core Django backend with tenant-isolated data models, JWT authentication, and encrypted Stripe token storage patterns,
So that every subsequent feature is built on enforced security and multi-tenancy from the first line of code.

**Acceptance Criteria:**

**Given** the Django backend is initialized
**When** I inspect the data models
**Then** a `TenantScopedModel` abstract base class exists with a required `account` FK
**And** a `TenantManager` replaces the default manager so `Model.objects.all()` always requires `account_id` scoping
**And** an `unscoped()` manager is available exclusively for admin/operator context

**Given** an `Account` and `User` model exist
**When** a new user is created
**Then** a corresponding `Account` record is created with a single `owner` FK to `User`
**And** the schema is designed so a future `Membership` join table can be added without migrating `Account` or `User` (NFR-SC3)

**Given** a client requests a protected API endpoint
**When** they present a valid JWT access token (15-min expiry)
**Then** the request succeeds and returns data scoped exclusively to their `account_id`
**And** when the access token is expired, a valid refresh token (7-day expiry) exchanges for a new one without re-login

**Given** the `StripeConnection` model stores a Stripe OAuth token
**When** the token is written to the database
**Then** it is encrypted via `cryptography.fernet` (AES-128-CBC + HMAC) before storage
**And** the `FERNET_KEY` is loaded exclusively from an environment variable — never from the database or committed to source control
**And** a database breach alone (without the env secret) cannot decrypt any stored token (NFR-S1)

**Given** any engine action, status change, or operator intervention occurs
**When** `write_audit_event(subscriber, actor, action, outcome, metadata)` is called
**Then** an `AuditLog` record is created with timestamp, actor (`engine`/`operator`/`client`), snake_case action verb, and outcome
**And** no `update` or `delete` path for `AuditLog` records exists in the application layer — append-only enforced (NFR-R3)

**Given** the Django admin is configured
**When** I navigate to `/ops-console/`
**Then** the Django admin interface is accessible to `is_staff=True` users only
**And** the standard `/admin/` path is disabled — not redirected, disabled
**And** all client accounts have `is_staff=False` (NFR-S4)

---

### Story 1.3: Decline-Code Rule Engine Config & Compliance Module

As a developer,
I want the decline-code rule engine defined as a data-driven config with a geo-compliance module,
So that all recovery logic is testable without a database and extensible without touching business logic code.

**Acceptance Criteria:**

**Given** the `core/engine/rules.py` module
**When** I inspect `DECLINE_RULES`
**Then** it contains entries for 30+ Stripe decline codes, each mapping to `{action, retry_cap, payday_aware, geo_block}`
**And** the following are explicitly correct: `card_expired` → `{notify_only, cap=0, payday_aware=False}`, `insufficient_funds` → `{retry_notify, cap=3, payday_aware=True, geo_block=True}`, `fraudulent` → `{fraud_flag, cap=0}`, `do_not_honor` → `{retry_notify, cap=2}`, `card_velocity_exceeded` → `{retry_notify, cap=1}`
**And** a `_default` catch-all maps unknown codes to `{retry_notify, cap=1, payday_aware=False, geo_block=False}` — never fraud-flags

**Given** `core/engine/compliance.py`
**When** `is_geo_blocked(payment_method_country, customer_billing_country)` is called with an EU or UK country code
**Then** it returns `True`, indicating retry must be blocked and routed to notify-only (FR13)
**And** when called with any non-EU/UK country, returns `False`

**Given** `core/engine/processor.py`
**When** `get_recovery_action(decline_code, payment_method_country, customer_billing_country)` is called
**Then** it returns the correct `action` from `DECLINE_RULES`, overriding to `notify_only` if geo-blocked
**And** the module has zero Django ORM imports — pure Python, no database dependency

**Given** the test suite at `backend/core/tests/test_engine/`
**When** I run `pytest core/tests/test_engine/`
**Then** all tests pass with no database connection required
**And** tests cover: correct action per code, geo-block override, `_default` fallback, fraud flag detection, payday-aware flag, retry cap values

---

### Story 1.4: Next.js Frontend Skeleton, Design Token System & State Management

As a developer,
I want the Next.js frontend initialized with SafeNet's design token system, shadcn/ui, and state management configured,
So that all subsequent UI stories build on a consistent, accessible, and theme-aware foundation.

**Acceptance Criteria:**

**Given** the Next.js app is initialized with TypeScript, Tailwind, App Router, ESLint, and `src/` directory
**When** I inspect `src/`
**Then** it contains: `app/` (routes + layouts), `components/ui/` (shadcn/ui primitives — never hand-edited), `components/common/`, `components/dashboard/`, `hooks/`, `stores/`, `lib/`, `types/`

**Given** the global CSS file
**When** I inspect it
**Then** all 12 semantic CSS custom properties are defined in both `:root` (light) and `.dark` (dark): `--bg-base`, `--bg-surface`, `--bg-elevated`, `--border`, `--text-primary`, `--text-secondary`, `--text-tertiary`, `--accent-recovery`, `--accent-active`, `--accent-fraud`, `--accent-neutral`, `--cta`, `--cta-hover`
**And** the Tailwind config extends these as semantic utility aliases
**And** Inter variable font is loaded with `font-variant-numeric: tabular-nums` applied to all monetary value display elements (UX-DR12)

**Given** shadcn/ui is initialized with the neutral theme
**When** I check `components/ui/`
**Then** the following are present: `Button`, `Badge`, `Card`, `Dialog`, `Sheet`, `Table`, `Checkbox`, `Toast`, `Popover`, `Select`, `Avatar`, `Separator`, `Input`, `Textarea`, `NavigationMenu`

**Given** a user makes an authenticated API request
**When** the axios instance in `src/lib/apiClient.ts` sends it
**Then** the JWT access token is injected via request interceptor
**And** a 401 response triggers a token refresh then retries the original request once
**And** if refresh fails, the user is redirected to the login screen

**Given** TanStack Query v5 is configured
**When** I inspect the app root layout
**Then** `QueryClientProvider` wraps the application with a 5-minute `staleTime` default for dashboard queries
**And** no `useState` is used anywhere for server data

**Given** Zustand stores are configured
**When** I inspect `src/stores/`
**Then** `uiStore` manages `activeSubscriberId`, `batchSelection`, and `themePreference`
**And** `authStore` manages JWT tokens and user identity

---

## Epic 2: Founder Onboarding & Free Tier Dashboard

A founder can connect their Stripe account, see a populated 90-day failure landscape immediately (no empty state), understand their recoverable revenue, and manage their subscription tier.

**FRs covered:** FR1, FR2, FR6, FR7, FR8, FR9, FR29, FR30, FR34, FR35, FR36, FR37, FR39, FR48
**UX-DRs covered:** UX-DR1, UX-DR2, UX-DR3, UX-DR5, UX-DR6, UX-DR7, UX-DR11, UX-DR13, UX-DR14, UX-DR18

### Story 2.1: User Registration & Stripe Connect OAuth

As a new founder,
I want to create a SafeNet account and connect my Stripe account via OAuth in a single flow,
So that I can access my payment failure data without handling any API keys.

**Acceptance Criteria:**

**Given** a new visitor on the SafeNet landing page
**When** they click "Connect with Stripe"
**Then** they are redirected through Stripe Express Connect OAuth (one click, no API key entry)
**And** on successful OAuth authorization, a `User` and `Account` record are created in SafeNet
**And** the Stripe access token is encrypted (AES-256 via Fernet) and stored in `StripeConnection` linked to the account (FR1, NFR-S1)

**Given** a new account is created
**When** the OAuth callback completes
**Then** the account is automatically on a 30-day Mid-tier trial with no payment method required (FR35)
**And** exactly one user (the owner) is associated with the account — no invitation or multi-user flow exists at this step (FR48)

**Given** the OAuth flow fails (user denies authorization)
**When** Stripe redirects back to SafeNet with an error
**Then** the user is returned to the landing page with a specific, human-readable error message
**And** no partial account or connection record is created

**Given** a user is already authenticated
**When** they navigate to any protected route
**Then** they are shown their dashboard — never redirected back through OAuth

---

### Story 2.1b: Post-OAuth Profile Completion & Login Flow Fix

As a new founder who just connected Stripe,
I want to set my name, company name, and password before seeing the dashboard,
So that my workspace is personalized, emails reference my brand, and I can log in with email/password on future visits.

**Acceptance Criteria:**

**Given** a new user completes Stripe OAuth authorization
**When** the callback succeeds and a new account is created
**Then** the user is redirected to `/register/complete` (not the dashboard)
**And** they see a form collecting: first name, last name, company/SaaS name, and password with confirmation (FR49)

**Given** the profile completion form
**When** the user submits valid data
**Then** the User record is updated with `first_name`, `last_name`, and a hashed password (Argon2)
**And** the Account record is updated with `company_name`
**And** Django's full password validation suite is applied server-side (min 8 chars, common password check, similarity check)
**And** `password` and `password_confirm` are validated to match server-side
**And** the endpoint rejects repeat submissions with 400 if profile is already completed
**And** the profile completion is recorded in the audit log via `write_audit_event()`
**And** the user is redirected to the dashboard

**Given** a returning user who has completed profile setup
**When** they visit the login page
**Then** they can log in with email and password
**And** receive JWT tokens and are redirected to the dashboard

**Given** an existing user with a completed profile
**When** they click "Connect with Stripe" on the login page
**Then** the OAuth callback recognizes their account by `stripe_user_id`
**And** issues JWT tokens and redirects to the dashboard (no profile re-prompt)
**And** this serves as a password recovery fallback (FR50)

**Given** a user who completed OAuth but abandoned profile completion
**When** they return (via Stripe re-auth or any authenticated route)
**Then** they are redirected to `/register/complete` — profile setup cannot be bypassed

**Given** the login endpoint and profile completion endpoint
**When** either receives requests
**Then** rate limiting is enforced: 5/min on login, 3/min on profile completion

**Technical notes:**
- Add `argon2-cffi` dependency; configure `Argon2PasswordHasher` as primary in `PASSWORD_HASHERS`
- Add `company_name` CharField(max_length=200) to Account model + migration
- New endpoint: `POST /api/v1/accounts/complete-profile/` (JWT auth required)
- Update `GET /api/v1/accounts/me/` to return `first_name`, `last_name`, `company_name`
- DRF `ScopedRateThrottle` on auth and profile endpoints
- Frontend `middleware.ts` checks profile completion, redirects if incomplete

---

### Story 2.2: 90-Day Retroactive Scan Background Job

As a newly connected founder,
I want SafeNet to automatically scan my last 90 days of Stripe payment failures immediately after connecting,
So that my dashboard is populated with real data before I take any action.

**Acceptance Criteria:**

**Given** a new Stripe Connect authorization completes
**When** the OAuth callback fires
**Then** a Celery background task (`scan_retroactive_failures`) is queued immediately for that account (FR2)
**And** the task fetches all payment intents from the past 90 days via the Stripe API using the encrypted access token

**Given** the retroactive scan task runs
**When** it processes each failed payment intent
**Then** it classifies the failure by Stripe decline code using `DECLINE_RULES` (FR7)
**And** it creates a `SubscriberFailure` record for each unique subscriber+failure combination, storing: `payment_intent_id`, `decline_code`, `amount_cents`, `subscriber_email`, `payment_method_country`, `created_at`, `account_id`
**And** zero raw card data is stored — only Stripe event metadata (NFR-S3)

**Given** the Stripe API rate limit is hit during the scan
**When** the task receives a rate limit error
**Then** it retries with exponential backoff — the scan never hard-fails due to temporary throttling (NFR-P4)

**Given** the retroactive scan completes
**When** the task finishes
**Then** first scan data is visible in the dashboard within 5 minutes of Stripe Connect authorization (NFR-P3)
**And** the dashboard UI is never blocked — the scan runs entirely as a background job (NFR-P2)
**And** a triggered onboarding email is sent to the client (FR34)

**Given** the daily polling job (`poll_new_failures`) is registered with Celery beat
**When** it runs every 24 hours (±2h tolerance)
**Then** it detects any new payment failures since the last poll for each connected account (FR6)
**And** if a polling cycle is missed, an operator alert fires within 30 hours (NFR-R1)
**And** rate limit errors trigger automatic retry — no cycle is abandoned due to throttling (NFR-P4)

---

### Story 2.3: Authenticated Dashboard Shell & Navigation

As an authenticated founder,
I want a persistent, responsive dashboard layout with always-visible engine status and workspace identity,
So that I always know SafeNet is running and can navigate confidently between sections.

**Acceptance Criteria:**

**Given** an authenticated user loads any dashboard page
**When** the page renders
**Then** the top navigation bar is visible with: `WorkspaceIdentity` (SafeNet wordmark + vertical divider + 2-letter SaaS monogram + SaaS name + "Marc's workspace"), `EngineStatusIndicator` (right-anchored), and user account menu (UX-DR6, UX-DR5)
**And** navigation tabs link to: Dashboard, Settings (and Review Queue when in Supervised mode)

**Given** the `EngineStatusIndicator`
**When** the engine is active (Autopilot or Supervised)
**Then** it displays an animated blue pulse dot + "Autopilot active" or "Supervised" + "Last scan Xm ago · next in Ym"
**And** when the engine is paused or errored, the dot is grey (paused) or amber (error) with appropriate status text
**And** status changes are announced via `aria-live="polite"` (UX-DR5, UX-DR13)

**Given** a desktop viewport (≥1280px)
**When** the dashboard renders
**Then** the full layout is shown: 48px topbar + full main content area (max-width 1280px, 32px padding)
**And** on tablet (768–1023px) the layout adapts; on mobile (<768px) the top nav is shown and complex actions (batch review, DPA signing) are not accessible — read-only view only (UX-DR14)

**Given** the light/dark theme toggle
**When** the user switches theme
**Then** all CSS custom properties update instantly via the `.dark` class on the root element
**And** the preference is persisted in `uiStore` and applied on next load

---

### Story 2.4: Failure Landscape Dashboard & KPI Cards

As a connected founder,
I want my dashboard to show a populated failure landscape with estimated recoverable revenue, decline-code breakdown, and the Story Arc 3-column layout,
So that I understand my payment health at a glance and the upgrade value is always visible.

**Acceptance Criteria:**

**Given** a client with completed retroactive scan data
**When** they load the dashboard
**Then** the `StoryArcPanel` renders 3 columns (Detected → In Progress → Recovered) via CSS Grid with 1px hairline dividers (UX-DR3)
**And** Column 1 shows total failures detected + subscriber count with neutral colour
**And** Column 2 shows estimated recoverable revenue (bold, 52px) + recovery rate as secondary KPI, in blue (FR9, UX-DR2)
**And** Column 3 shows recovered this month in green (56px Inter 700) + retry count + net benefit (UX-DR2)

**Given** the dashboard API endpoint `/api/v1/dashboard/summary/`
**When** called
**Then** it returns aggregated KPIs in `{data: {...}}` envelope with all monetary values as integer cents
**And** the response is cached with a 5-minute TTL in Redis, invalidated on any new engine action for that account
**And** it responds within 3 seconds for accounts with up to 500 subscribers (NFR-P1)

**Given** a free-tier client viewing the dashboard
**When** the estimated recoverable revenue figure is visible
**Then** a single upgrade CTA is anchored directly below it: "Activate recovery engine — €29/month" (FR39, FR9)
**And** no other primary CTA competes for attention on the same screen

**Given** the failure breakdown section (FR8, FR30)
**When** rendered below the StoryArcPanel
**Then** each decline code category is shown with a plain-language label via `DeclineCodeExplainer` (e.g., "Card expired", "Insufficient funds") — no raw Stripe codes visible (UX-DR7)
**And** each category shows subscriber count, total amount at risk, and a colour-coded indicator

**Given** the dashboard is loading
**When** TanStack Query is fetching data
**Then** skeleton screens mirror the exact shape of loaded content: 3 StoryArc column skeletons + 6 SubscriberCard skeletons (UX-DR11)
**And** the dashboard never shows an empty state after a completed scan — data is always present (FR29, UX-DR18)

**Given** all interactive elements on the dashboard
**When** navigated via keyboard
**Then** all have visible focus rings using `--accent-active` colour
**And** all KPI numbers have `aria-label` with currency and context (e.g., "€640 estimated recoverable revenue")
**And** scan animations and transitions respect `prefers-reduced-motion` (UX-DR13)

---

### Story 2.5: Subscription Tiers, Trial Mechanics & Free-Tier Degradation

As a founder,
I want SafeNet to manage my trial period automatically and clearly communicate my tier status and limitations,
So that I understand what I have access to and can upgrade when ready.

**Acceptance Criteria:**

**Given** a new account is created via Stripe Connect
**When** the account is provisioned
**Then** it is placed on a 30-day Mid-tier trial with full email-send access and no payment method required (FR35)
**And** polling runs at daily frequency during the trial period

**Given** a trial account reaches day 30 without upgrading
**When** the trial expiration job runs
**Then** the account is automatically downgraded to Free tier (FR36)
**And** polling frequency drops to weekly
**And** the dashboard displays the degradation prominently: "Your next scan is in X days" (FR37)
**And** email sending is deactivated — no new dunning emails dispatched. Free tier shows the failed-payments list view-only.

**Given** a Free-tier client views their dashboard
**When** the tier indicator is rendered
**Then** the "estimated recoverable revenue" figure remains visible and accurate (permanent Free-tier feature)
**And** a single upgrade CTA is anchored below it (FR39)
**And** the next scan countdown is visible without scrolling (FR37)

**Given** a client clicks the upgrade CTA and completes Stripe Billing checkout
**When** the subscription is confirmed via Stripe webhook
**Then** the account is immediately upgraded to Mid tier
**And** daily polling resumes
**And** the DPA acceptance gate is presented before the first email send if not previously signed

---

## Epic 3 (v0): Recovery Engine, Compliance & Customer Status Management — QUARANTINED

> **⚠️ QUARANTINED 2026-04-29.** This epic and all 5 stories below (3.1, 3.2, 3.3, 3.4, 3.5) are preserved on branch `archive/v0-recovery-engine` and are **not in the v1 product**. Reference: `_bmad-output/sprint-change-proposal-2026-04-29.md`.
>
> The simplified v1 Epic 3 follows immediately after this section.

A Mid-tier client can activate the recovery engine (with DPA gate and mode selection), which then classifies failures, applies code-aware rules, enforces geo-compliance, manages the 4-state customer status machine, detects fraud, and handles card-update triggered retries.

**FRs covered:** FR3, FR4, FR5, FR10, FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR46, FR47
**UX-DRs covered:** UX-DR4, UX-DR8, UX-DR9, UX-DR10, UX-DR15, UX-DR16

### Story 3.1: DPA Acceptance & Engine Mode Selection Flow

As a Mid-tier founder,
I want to review and formally accept the Data Processing Agreement, then choose my recovery mode,
So that I understand what SafeNet processes on my behalf and explicitly authorize the engine to act.

**Acceptance Criteria:**

**Given** a Mid-tier client clicks "Activate recovery engine"
**When** the activation flow begins
**Then** a full-page DPA screen is presented — not a checkbox, not a modal embedded in a form (FR3, UX-DR15)
**And** the DPA screen documents: what SafeNet processes, on whose behalf, for what purpose, with what retention policy, and under what security measures

**Given** the DPA screen
**When** the client clicks "I accept and sign"
**Then** a `DPAAcceptance` record is created with timestamp and account FK
**And** the client is advanced to the mode selection screen — the engine does NOT activate yet

**Given** the mode selection screen
**When** the client reviews their options
**Then** Autopilot is described as: "SafeNet handles all recovery automatically — no action required from you"
**And** Supervised is described as: "SafeNet queues actions for your review before executing"
**And** a plain-language consequence statement is shown for each before the client confirms (FR4)

**Given** the client selects a mode and confirms
**When** the mode is saved
**Then** the recovery engine is activated for that account
**And** the `EngineStatusIndicator` updates to: "Autopilot active — next scan in 60 min" or "Supervised — review queue enabled"
**And** the client can switch modes at any time from Settings without re-signing the DPA (FR5)

**Given** the client exits the DPA screen without accepting
**When** they return to the dashboard
**Then** they remain on Free tier
**And** a non-intrusive reminder is shown on next login: "Sign the DPA to activate your recovery engine"

---

### Story 3.2: Autopilot Recovery Engine: Rule Execution & 4-State Status Machine

As a founder on Autopilot,
I want SafeNet to automatically process every failed payment using the correct recovery rule and track each subscriber's status through the 4-state machine,
So that recovery happens without my involvement and every outcome is auditable.

**Acceptance Criteria:**

**Given** a new `SubscriberFailure` is detected by the polling job
**When** the rule engine processes it via `get_recovery_action(decline_code, ...)`
**Then** the correct action is applied per `DECLINE_RULES`: `retry_only`, `notify_only`, `retry_notify`, `fraud_flag`, or `no_action` (FR10)
**And** the subscriber's initial status is set to `active` via `django-fsm` (FR16)

**Given** an `insufficient_funds` failure in Autopilot mode
**When** the retry scheduler runs
**Then** the retry is queued within a 24-hour window after the 1st or 15th of the month — whichever comes next (FR11)
**And** the retry cap of 3 attempts is enforced for this code (FR12)

**Given** a `geo_block=True` rule for a payment from an EU/UK country
**When** the engine processes the failure
**Then** no retry is queued — the action is overridden to `notify_only` regardless of the decline code's default action (FR13)
**And** the override is recorded in the audit log

**Given** a retry attempt succeeds (Stripe confirms payment)
**When** the engine processes the success
**Then** the subscriber transitions from `active` → `recovered` via the FSM (FR17)
**And** the post-transition signal automatically writes an audit event: `{action: "status_recovered", actor: "engine", outcome: "success"}` (NFR-R3)

**Given** the retry cap is exhausted with no recovery
**When** the engine processes the final failed attempt
**Then** the subscriber transitions from `active` → `passive_churn` (FR18)
**And** the audit log records the transition with the final decline code and attempt count

**Given** a `fraudulent` decline code is detected
**When** the engine classifies the failure
**Then** the subscriber is immediately set to `fraud_flagged` status (FR19)
**And** all further actions (retries, notifications) are stopped for this subscriber — no exceptions
**And** the audit log records: `{action: "status_fraud_flagged", actor: "engine", outcome: "success", metadata: {decline_code: "fraudulent"}}`

**Given** a subscriber's Stripe subscription transitions to `cancelled`, `unpaid`, `paused`, or `cancel_at_period_end`
**When** the polling job detects this state
**Then** all recovery actions for that subscriber are stopped
**And** the subscriber transitions to `passive_churn` with the specific reason recorded (FR46)

**Given** a Celery task for retry execution fails with an unhandled exception
**When** the exception is caught
**Then** it is written to `DeadLetterLog` with task name, account ID, and error string (NFR-R5)
**And** the failure is surfaced for operator review — never silently dropped (NFR-R3)

---

### Story 3.3: Card-Update Detection & Immediate Retry

As a founder,
I want SafeNet to detect when a subscriber updates their payment method and immediately retry their most recent failure,
So that recoveries happen as soon as the subscriber takes action — without waiting for the next scheduled retry window.

**Acceptance Criteria:**

**Given** a subscriber with `active` status has a pending `SubscriberFailure`
**When** the hourly polling job detects that the subscriber's Stripe payment method has been updated
**Then** an immediate retry is queued for their most recent active failure — independent of the payday-aware schedule (FR47)
**And** the retry is logged in the audit trail with `{action: "retry_queued", metadata: {trigger: "card_update_detected"}}`

**Given** the immediate retry fires
**When** Stripe confirms or declines the payment
**Then** the outcome is processed by the standard state machine (→ `recovered` on success, re-evaluated on decline)
**And** if successful, the recovery confirmation email flow is triggered (handled by Epic 4)

**Given** a subscriber updates their card but has no active-status failure
**When** the polling job detects the card update
**Then** no retry is queued — the detection only applies to subscribers in `active` status

---

### Story 3.4: Supervised Mode: Pending Action Queue & Batch Approval

As a founder in Supervised mode,
I want to review all pending recovery actions with pre-selected recommendations before they execute,
So that I stay in control of edge cases without having to configure anything from scratch.

**Acceptance Criteria:**

**Given** a new failure is detected for an account in Supervised mode
**When** the engine processes it
**Then** the action is added to the pending queue rather than executed immediately (FR14)
**And** the `EngineStatusIndicator` badge count increments to reflect pending reviews

**Given** the Supervised review queue screen
**When** the client opens it
**Then** each row shows: subscriber name, plain-language decline reason, recommended action (pre-selected per decline code), and amount at risk (UX-DR16)
**And** all rows are pre-selected by default — the client reviews, not configures

**Given** the client selects rows and clicks "Apply recommended actions"
**When** the `POST /api/v1/actions/batch/` endpoint is called
**Then** all selected actions are queued for execution
**And** a toast confirms: "N actions queued"
**And** partial batch failure is surfaced with a warning toast — not silently swallowed (UX-DR8)

**Given** the client selects a subscriber and clicks "Exclude from automation"
**When** the exclusion confirmation dialog is accepted
**Then** that subscriber is excluded from all future automated retries and notifications
**And** the exclusion is recorded in the audit log
**And** the subscriber is removed from the review queue

**Given** the review queue is empty
**When** all pending actions have been processed
**Then** the zero-state renders: "Nothing needs your eyes right now. Approved items and automated recoveries are handled." (UX-DR18)

---

### Story 3.5: Subscriber Status Cards & Attention Bar

As a founder,
I want to see subscriber recovery statuses clearly on the dashboard with immediate visibility into items requiring attention,
So that I can spot fraud flags and urgent cases without scanning the entire subscriber list.

**Acceptance Criteria:**

**Given** the dashboard loads with subscriber data
**When** the subscriber grid renders
**Then** each subscriber is shown as a `SubscriberCard`: name (bold), amount (right-aligned), email sub-label, plain-language decline reason, and a status `Badge` (UX-DR9)
**And** the 4 badge variants are applied correctly: Recovered (green, `--accent-recovery`), Active (blue, `--accent-active`), Fraud Flagged (red, `--accent-fraud`), Passive Churn (grey, `--accent-neutral`) — each with a text label, never colour-only (FR16, UX-DR10)
**And** attention-state cards (fraud flags, Supervised pending) always render first in the grid regardless of sort order

**Given** one or more items require the client's attention (fraud flag, supervised pending, retry cap approaching)
**When** the dashboard renders
**Then** the `AttentionBar` appears as an amber strip below the topbar with: warning icon, "N items need your attention", "Review before next engine cycle in Xm", and named action pills (clickable chips) (UX-DR4)
**And** clicking a pill navigates to the relevant subscriber detail or review queue
**And** the bar is hidden when no attention items exist
**And** `role="alert"` with `aria-live="polite"` is set on the bar (UX-DR13)

**Given** a `fraud_flagged` subscriber card
**When** rendered
**Then** it displays an amber border + "⚠ Fraud flagged" label (distinct from the red badge — the amber border signals "needs attention")
**And** it appears first in the subscriber grid

---

## Epic 3 (v1): DPA Gate, Failed-Payments Dashboard & Email Actions

A Mid-tier client signs the DPA, then opens their dashboard to see all current-month failed payments with a recommended dunning email per row. They click to send (single or batch), choose a different email type if they prefer, or mark a failure as resolved. Status transitions are polling-detected (Active → Recovered / Passive Churn) and Marc-initiated (manual resolve, exclude). No automated retries; no autopilot/supervised duality.

**FRs covered:** FR3, FR10, FR16, FR17, FR18, FR19, FR52, FR53, FR54, FR55
**UX-DRs covered:** UX-DR4 (simplified), UX-DR8 (reframed), UX-DR9, UX-DR10, UX-DR15

### Story 3.1 (v1): DPA Acceptance Gate

As a Mid-tier founder,
I want to formally sign the Data Processing Agreement before SafeNet sends emails to my subscribers,
So that I understand what SafeNet processes on my behalf and explicitly authorize the email-send capability.

**Acceptance Criteria:**

**Given** a client attempts to dispatch their first dunning email (per-row or bulk)
**When** the dispatch endpoint is called and no `DPAAcceptance` record exists for the account
**Then** the API rejects the send with a `403 DPA_REQUIRED` envelope
**And** the frontend shows the DPA screen (not a modal embedded in a form) before any send button becomes active

**Given** the DPA screen
**When** the client clicks "I accept and sign"
**Then** a `DPAAcceptance` record is created with timestamp, account FK, and the DPA version hash
**And** the client is returned to the failed-payments dashboard with send buttons enabled

**Given** an account that signed the v0 DPA before 2026-04-29
**When** they next log in
**Then** the v0 DPA acceptance is honored without re-acceptance (DPA version hash carries forward)

**Given** Settings → Account
**When** the client views the page
**Then** DPA acceptance status is displayed: signed-on date and DPA version

**Given** the client has not signed the DPA
**When** they navigate the dashboard
**Then** the failed-payments list is fully visible (view-only)
**And** every send button shows a tooltip "Sign the DPA to enable email sends" and is disabled

---

### Story 3.2 (v1): Current-Month Failed-Payments Dashboard

As a Mid-tier founder,
I want a dashboard view of all failed payments from the current month with recommended emails per row,
So that I can review and act on each at my own pace.

**Acceptance Criteria:**

**Given** the dashboard loads
**When** the failed-payments list renders
**Then** rows are filtered to `failure_created_at` within the current calendar month (account timezone)
**And** each row displays: subscriber name + email, amount in cents formatted to €, plain-language decline reason via `DeclineCodeExplainer`, recommended email type chip, status badge (Active / Recovered / Passive Churn / Fraud Flagged), and last-email-sent timestamp if any

**Given** the failed-payments list
**When** the client clicks the column headers
**Then** the list sorts by amount (desc/asc) or date (desc/asc) — selection persists in URL query params

**Given** a Free-tier client
**When** they view the failed-payments list
**Then** action buttons (Send, Mark resolved, Exclude) are disabled with an upgrade CTA tooltip

**Given** zero failed payments for the current month
**When** the list renders
**Then** the empty state shows: "No failed payments this month."

**Given** a `fraud_flagged` row
**When** rendered
**Then** the recommended email chip displays "—" (no recommendation)
**And** the row has an amber border to distinguish it from regular Active rows

---

### Story 3.3 (v1): Per-Row Send & Manual Resolve

As a Mid-tier founder,
I want to trigger a recommended (or chosen) dunning email per failed-payment row, and to manually mark failures as resolved,
So that I act on each case without leaving the dashboard.

**Acceptance Criteria:**

**Given** a row with status `Active` and a non-null recommended email type
**When** the client clicks "Send recommended"
**Then** `POST /api/v1/subscribers/{id}/send-email/` is called with `{email_type: <recommended>}`
**And** the dispatch service runs the opt-out check, then queues the Resend send
**And** the audit log records `{action: "email_sent", email_type, trigger: "client_manual"}` (FR53)

**Given** a row with status `Active`
**When** the client opens the per-row dropdown "Send specific email"
**Then** options shown are: Update payment / Retry reminder / Final notice
**And** selecting any option sends that email type via the same endpoint (FR53)

**Given** a row with any status
**When** the client clicks "Mark resolved"
**Then** the subscriber transitions to `Recovered` status with a manual-resolution audit note
**And** the row's badge updates to Recovered (FR55)

**Given** a row
**When** the client clicks "Exclude from future recommendations"
**Then** future recommendations for this subscriber are suppressed (recommended_email returns null)
**And** the exclusion is recorded in the audit log

**Given** an opted-out subscriber
**When** the client triggers any send for that subscriber's row
**Then** the dispatch service rejects the send with a clear error
**And** no Resend call is made (FR26, FR27)

**Given** an account hitting the rate limit (10 sends/min)
**When** the client triggers an 11th send within the window
**Then** the API responds 429 with retry-after seconds
**And** the frontend surfaces a non-blocking toast

---

### Story 3.4 (v1): Bulk Send & Status Polling

As a Mid-tier founder,
I want to bulk-send dunning emails for multiple selected rows, and trust SafeNet to detect when subscribers pay or cancel through daily polling,
So that I cover the high-leverage moves quickly without micromanaging each subscriber.

**Acceptance Criteria:**

**Given** the failed-payments list
**When** the client selects rows via the checkbox column
**Then** the bulk action toolbar slides up showing the selected count
**And** primary action: "Send recommended (N)"
**And** secondary action: "Send specific (chosen type)"
**And** tertiary actions: "Mark resolved (N)", "Exclude (N)" (FR54)

**Given** the client clicks "Send recommended (N)"
**When** the confirmation dialog opens
**Then** it shows the N rows with each row's recommended email type pre-listed
**And** a "Send all" button confirms the bulk dispatch

**Given** the bulk send confirms
**When** `POST /api/v1/subscribers/batch-send-email/` is called
**Then** each row dispatches with its own email type
**And** partial failures surface per-row in a result toast (UX-DR8 reframed)
**And** the audit log records one entry per send

**Given** the daily polling Celery task runs
**When** it detects a subscription state of `cancelled`, `unpaid`, `paused`, or `cancel_at_period_end`
**Then** the subscriber transitions Active → Passive Churn with the specific reason recorded (FR18)

**Given** the daily polling Celery task runs
**When** it detects a previously-failed PaymentIntent now succeeded
**Then** the subscriber transitions Active → Recovered (FR17)
**And** the recovery confirmation email is dispatched per FR25 (Story 4.3)

**Given** Free-tier client
**When** they attempt to multi-select
**Then** the bulk toolbar surfaces an upgrade CTA; bulk send is paid-only

---

### Story 3.5 (v1): Recommended-Email Mapping (Decline Code → Email Type)

As a developer,
I want the rule engine to map each decline code to a recommended email type and time-since-failure escalation,
So that the dashboard's per-row recommendation is data-driven and testable.

**Acceptance Criteria:**

**Given** the `DECLINE_RULES` config
**When** loaded
**Then** the action vocabulary is `{update_payment, retry_reminder, final_notice, fraud_flag, no_recommendation}` (FR10)
**And** retry_cap, payday_aware, geo_block fields remain in the config but are not consulted in v1 (v2 reactivation-ready)

**Given** a failure
**When** `get_recommended_email(decline_code, days_since_failure)` is called
**Then** day 0–6 returns `update_payment`
**And** day 7–13 returns `retry_reminder`
**And** day 14+ returns `final_notice`
**And** `fraudulent` decline code returns `fraud_flag` (no recommendation)
**And** unknown decline codes via `_default` return `update_payment`

**Given** the recommended email logic
**When** unit tests run via pytest
**Then** the module is pure-Python, zero DB dependency, fully exercisable without fixtures
**And** branch coverage ≥95% for the recommendation function

**Given** a `SubscriberFailure` row serialized for the frontend
**When** the response is built
**Then** the response includes `recommended_email_type` derived from the rule engine + time-since-failure
**And** `geo_warning: true` is included for SEPA/UK payment-method countries (informational only)

---

## Epic 4: End-Customer Notification System

Mid-tier clients' subscribers receive compliant, branded email notifications — making the end-customer experience indistinguishable from a well-run in-house billing operation.

**FRs covered:** FR22, FR23, FR24, FR25, FR26, FR27, FR28, FR50, FR51, FR56
**UX-DRs covered:** UX-DR17

### Story 4.1: Resend Integration & Branded Failure Notification Email

As a Mid-tier founder,
I want SafeNet to send a branded payment failure notification to my subscriber using my SaaS name when I trigger it,
So that my subscriber receives a professional, human-feeling email that feels like it came from me.

**Acceptance Criteria:**

**Given** the Resend email provider is configured
**When** a client triggers a dunning email send via the failed-payments dashboard (per-row or batch action)
**Then** the email is sent from the SafeNet-managed shared sending domain (`payments.safenet.app`) with the client's brand name in the `From` field (e.g., "ProductivityPro via SafeNet") (FR28)
**And** the email contains: a clear explanation of the failure (plain language, no Stripe jargon), a single card-update CTA linking to the configured redirect link (FR51), an opt-out link, and the client's brand name throughout (FR22, FR26)

> **Trigger note:** The engine-driven auto-trigger path is quarantined to `archive/v0-recovery-engine`. v1 sends are exclusively client-initiated via the failed-payments dashboard.

**Given** a `card_expired` failure
**When** the notification email is sent
**Then** the email explicitly states: "Your access continues while you update your details"
**And** the subject line is understated — no urgency language, no threat of account suspension

**Given** a notification send attempt fails (Resend API error)
**When** the task catches the exception
**Then** it retries up to 3 times with exponential backoff
**And** if all retries fail, the failure is written to `DeadLetterLog` and the audit log records `{action: "notification_failed", outcome: "failed"}` (NFR-R3)

---

### Story 4.2: Tone Selector Settings & Live Notification Preview

As a Mid-tier founder,
I want to choose my notification tone from three presets and see exactly what my subscribers will receive,
So that the emails reflect my brand voice before any subscriber sees them.

**Acceptance Criteria:**

**Given** the Settings → Notifications screen
**When** the client selects a tone preset (Professional / Friendly / Minimal)
**Then** a live preview updates immediately — showing exactly what their subscriber will receive, with the client's brand name populated (FR23, UX-DR17)
**And** the preview updates on every preset change without a page reload

**Given** the client saves a tone selection
**When** the engine next sends a notification for that account
**Then** the email body uses the template for the selected tone preset
**And** the tone can be changed at any time — the next notification uses the new tone

**Given** the three tone presets
**When** rendered in the preview
**Then** Professional: formal, direct, no contractions; Friendly: warm, conversational; Minimal: bare facts, two sentences maximum
**And** all three tones comply with GDPR transactional classification — zero marketing content

**Given** the Settings → Notifications screen
**When** the client views the redirect link section
**Then** an input field shows the redirect link (URL, defaults to the Stripe customer portal URL)
**And** the client can edit it; on save, validation enforces `https://` scheme + reachable URL pattern
**And** the link is embedded in all subsequent dunning emails as the subscriber's "update payment" CTA target (FR51)

**Given** a paid-tier (Mid or Pro) client on the Settings → Notifications screen
**When** they expand the "Custom email body" section
**Then** they see three textarea editors: Update payment / Retry reminder / Final notice
**And** each starts pre-filled with the current tone-preset's default body
**And** they can edit each independently; on save, the custom body overrides the tone preset for that email type (FR56)
**And** Free-tier clients see the editors disabled with an upgrade CTA

---

### Story 4.3: Final Notice & Recovery Confirmation Emails

As a Mid-tier founder,
I want SafeNet to send a final notice before a subscriber graduates to Passive Churn, and a confirmation email when a payment is recovered,
So that every outcome is communicated clearly and the subscriber relationship is handled with dignity.

**Acceptance Criteria:**

**Given** a subscriber row on the failed-payments dashboard
**When** the client triggers a "Final notice" email type for that row (per-row or via bulk action with email type "Final notice" chosen)
**Then** a final notice email is sent to the subscriber (FR24)
**And** the email states explicitly and honestly: "This is our last attempt to remind you about your unpaid invoice. Please update your payment method to keep your subscription active."
**And** the selected tone preset is applied (or the custom body, if a paid-tier override is configured)

**Given** the daily polling job detects a previously-failed PaymentIntent has succeeded, OR the client manually marks the failure as resolved
**When** the status transition is recorded
**Then** a recovery confirmation email is sent to the subscriber within the next polling cycle (FR25)
**And** the email is brief (two sentences maximum): "All sorted — payment confirmed. Thanks for updating your details."

**Given** either email type
**When** rendered
**Then** an opt-out link is present and functional (FR26)
**And** the sender identity is the client's brand via the SafeNet shared domain (FR28)
**And** the configured redirect link is embedded as the "update payment" CTA target (FR51)

> **Trigger note:** FSM auto-transition signal trigger (`is_last_retry`, retry-success post-transition signal) is quarantined to `archive/v0-recovery-engine`. v1 final notice is client-triggered; v1 recovery confirmation is polling-detected or manual-resolve-driven.

---

### Story 4.4: Opt-Out Mechanism & Notification Suppression

As a subscriber,
I want to opt out of payment notifications from a specific SaaS using SafeNet,
So that my communication preferences are respected without affecting my account access.

**Acceptance Criteria:**

**Given** every notification email sent by SafeNet
**When** the subscriber clicks the opt-out link
**Then** a `NotificationOptOut` record is created linking subscriber email to client account
**And** a confirmation page is shown: "You've been unsubscribed from payment notifications for [SaaS name]."
**And** the opt-out is recorded in the audit log (FR26)

**Given** a subscriber has opted out for a specific client account
**When** the engine attempts to send any notification to that subscriber for that account
**Then** the notification is suppressed — not sent (FR27)
**And** the suppression is logged: `{action: "notification_suppressed", metadata: {reason: "opted_out"}}`
**And** a standard marketing opt-out from the client's own communications does NOT suppress SafeNet notifications — SafeNet opt-out is managed independently (FR27)

**Given** the engine checks opt-out status
**When** evaluating whether to send a notification
**Then** the opt-out check occurs before every notification action — no notification is ever sent without this check
**And** the check is scoped per subscriber+account pair (not globally across accounts)

---

### Story 4.5: Email-Based Password Reset Flow

As a founder who has forgotten my password,
I want to reset it via email,
So that I can regain access to my account without re-authorizing through Stripe.

**Acceptance Criteria:**

**Given** the login page
**When** a user clicks "Forgot password?"
**Then** they are prompted to enter their email address
**And** a password reset email is sent via Resend (same transactional email provider as notifications)
**And** the response is generic regardless of whether the email exists ("If an account exists, we've sent a reset link") — no email enumeration

**Given** a valid password reset email
**When** the user clicks the reset link
**Then** they are taken to a password reset form with a time-limited token (1 hour expiry, single-use)
**And** the token is generated via Django's `PasswordResetTokenGenerator` (no DB storage needed)

**Given** the password reset form
**When** the user submits a new password
**Then** the password is validated (same rules as profile completion: min 8 chars, Django validators)
**And** the password is updated and the reset token is invalidated
**And** the event is recorded in the audit log

**Given** password reset requests
**When** rate limiting is checked
**Then** a maximum of 3 reset requests per email per hour is enforced

**Technical notes:**
- Uses Resend infrastructure from Story 4.1
- Django's `PasswordResetTokenGenerator` for signed, time-limited tokens
- No additional DB models needed — tokens are stateless (signed with SECRET_KEY)
- Audit log: `action="password_reset_requested"` and `action="password_reset_completed"`

---

## Epic 5: Subscriber Detail, Analytics & Retention Emails

A client can drill into any individual subscriber's payment history, resolve fraud flags, receive a weekly digest, and benefit from automated retention/email purges. Recovery analytics + month-over-month dashboard and the monthly-savings email are deferred to v2 — both depended on auto-recovery semantics that the v1 simplification removed.

**FRs covered:** FR20, FR21, FR33
**Deferred to v2:** FR31, FR32, FR38
**NFRs:** NFR-D1, NFR-D2, NFR-D3

### Story 5.1: Subscriber Detail Panel & Payment Timeline

As a founder,
I want to open any subscriber's detail panel and see their complete payment history, decline events, and current status in one place,
So that I can understand exactly what happened to each subscriber and have full context for any manual decision.

**Acceptance Criteria:**

**Given** a client clicks any subscriber card on the dashboard
**When** the subscriber detail `Sheet` opens (slides from right)
**Then** it displays: subscriber name + email, current status badge, full payment history (all charge attempts chronologically), each failure's decline code with plain-language explanation, all email send history (per email type, timestamps), status transitions, and manual notes (FR20)
**And** the data is fetched from `GET /api/v1/subscribers/{id}/timeline/` in a single request — no secondary fetches required

**Given** a subscriber with `fraud_flagged` status
**When** their detail panel opens
**Then** the top of the panel shows a status block: "Payment flagged as fraud by card issuer. SafeNet has stopped all automated actions for this subscriber."
**And** the plain-language explanation of the `fraudulent` decline code is shown via `DeclineCodeExplainer`
**And** "Mark as reviewed" is the only action available — no retry button, no re-enable automation button

**Given** the Sheet component
**When** used for subscriber detail
**Then** it closes on backdrop click or the × button — no browser back button dependency
**And** closing the Sheet returns focus to the subscriber card that was clicked (UX-DR13)

---

### Story 5.2: Fraud Flag Manual Resolution

As a founder,
I want to manually resolve a fraud-flagged subscriber with an optional note,
So that the case is formally closed in the audit trail and I can move on with full documentation.

**Acceptance Criteria:**

**Given** a `fraud_flagged` subscriber's detail panel
**When** the client clicks "Mark as reviewed"
**Then** an optional note field is shown (multiline textarea, auto-focusing cursor, character count at 80% of limit)
**And** the client can confirm resolution with or without a note (FR21)

**Given** the client confirms resolution
**When** the resolution is saved
**Then** `write_audit_event(subscriber, actor="client", action="fraud_flag_resolved", outcome="success", metadata={note: "..."})` is called
**And** the subscriber's status is updated — the UI reflects the resolved state immediately
**And** the resolution appears in the subscriber's timeline in the detail panel

**Given** the resolution is confirmed
**When** the panel updates
**Then** the fraud flag is cleared from the `AttentionBar` (if it was listed there)
**And** the subscriber card no longer shows the amber attention border

---

### Story 5.3: Recovery Analytics & Month-over-Month Dashboard — DEFERRED TO V2

> **Deferred under 2026-04-29 simplification** — the analytics framing depended on the auto-recovery engine ("retries fired", "notifications that drove card updates"). Reframe + reactivate when v1 has real send-volume data.

As a founder,
I want to view recovery analytics and month-over-month trends in my dashboard,
So that I can track SafeNet's performance over time and have data to justify the subscription cost.

**Acceptance Criteria:**

**Given** a Mid-tier client with at least one completed recovery cycle
**When** they navigate to the Analytics section
**Then** they can view: total payments recovered (count + amount), successful retry attempts, notifications that drove card updates, and recovery rate percentage (FR31)

**Given** the month-over-month comparison view (FR32)
**When** rendered
**Then** it shows side-by-side comparison for the current and previous month: failure rate, recovery rate, revenue protected (€), and Passive Churn count
**And** monetary values use `font-variant-numeric: tabular-nums` for vertical alignment

**Given** the analytics data is fetched
**When** the API responds
**Then** all monetary values are integer cents in the response, formatted to € in the display layer only
**And** the dashboard loads within 3 seconds for accounts with up to 500 subscribers (NFR-P1)

---

### Story 5.4: Weekly Digest Email & Data Retention (Monthly Savings — Deferred)

> **Split under 2026-04-29 simplification:** Weekly digest + retention purge stay in v1. Monthly savings email is deferred to v2 (recovery framing changes when sends are client-initiated; defer one cycle and revisit with real data).

As a founder,
I want to receive automated emails summarizing SafeNet's activity and proven value,
So that I stay informed passively and have clear evidence of ROI without checking the dashboard.

**Acceptance Criteria:**

**Given** a Mid-tier client with the weekly digest enabled (off by default)
**When** the weekly digest job runs (every Monday)
**Then** an email is sent summarizing: dunning emails sent that week (per type), payments recovered (polling-detected + manually-resolved), and new Passive Churn flags that week (FR33)
**And** the digest is sent only to clients who have explicitly opted in via Settings → Notifications

> **Monthly savings email (FR38) — DEFERRED to v2.** Reframe in v2 when send-volume data is available.

**Given** payment event metadata in the database
**When** an event's `created_at` is more than 24 months ago
**Then** a scheduled purge job deletes the record (NFR-D1)
**And** the corresponding `AuditLog` records are retained for 36 months — not purged with event data (NFR-D2)

**Given** a subscriber reaches `passive_churn` status
**When** 30 days have elapsed since the status change
**Then** the subscriber's email address is purged from SafeNet's database (NFR-D3)
**And** the purge is recorded in the audit log: `{action: "email_purged", actor: "system", outcome: "success"}`

---

## Epic 6: Operator Administration Console

The SafeNet operator can review the full audit trail, manually advance subscriber statuses for edge cases, and inspect email-send history — with strict access control ensuring no client reaches operator capabilities. Scheduled-retry dashboard removed: no retries to schedule in v1.

**FRs covered:** FR42, FR43, FR44, FR45
**Deferred to v2:** FR40, FR41
**NFRs:** NFR-S4, NFR-R3, NFR-R5

### Story 6.1: Operator Authentication & Console Access Isolation

As the SafeNet operator,
I want a dedicated console accessible only to authenticated operator accounts,
So that clients can never access operator capabilities regardless of how they navigate.

**Acceptance Criteria:**

**Given** the Django admin is mounted at `/ops-console/`
**When** a non-operator (client) user attempts to access `/ops-console/`
**Then** they receive a 403 or redirect to the client login — not the operator login (FR45, NFR-S4)
**And** the standard `/admin/` path returns 404 — it is disabled, not redirected

**Given** an operator with `is_staff=True` logs in to `/ops-console/`
**When** they authenticate
**Then** they have access to all operator capabilities: manual status advancement, audit log viewer, email-send history per account
**And** no client-facing data modification is possible from operator routes

**Given** a client account
**When** inspected in the database
**Then** `is_staff` is always `False` — no client account can be escalated to operator access through any client-facing flow

---

### Story 6.2: Scheduled Retry Dashboard & Manual Override — DEFERRED TO V2

> **Deferred under 2026-04-29 simplification.** No retries to schedule in v1. The full operator workflow described in this story applies only to the v2 quarantine branch (`archive/v0-recovery-engine`). Retain the original spec text below as v2 inventory; do not implement on main.

As the SafeNet operator,
I want to see all retries scheduled to fire across all accounts and cancel any that look problematic before they execute,
So that I can intervene on edge cases without waiting for clients to report issues.

**Acceptance Criteria (v2-only — not in v1 product):**

**Given** the operator console retry dashboard
**When** I view it
**Then** I can see all retries scheduled to fire within the next 24 hours across all client accounts, including: account name, subscriber email, decline code, scheduled fire time, and retry attempt number (FR40)
**And** retries are sortable by scheduled time and filterable by account

**Given** a scheduled retry that looks problematic
**When** I click "Cancel retry" and enter a reason
**Then** the retry is cancelled and removed from the execution queue (FR41)
**And** `write_audit_event(subscriber, actor="operator", action="retry_cancelled", outcome="success", metadata={reason: "..."})` is called
**And** the cancellation is visible in the subscriber's timeline in the audit log

**Given** the retry scheduler runs every minute via Celery beat
**When** a retry is cancelled
**Then** it does not fire — even if the cancellation happened within the scheduled window (≤15 min variance still applies to non-cancelled retries) (NFR-R2)

---

### Story 6.3: Manual Status Advancement & Audit Log Viewer

As the SafeNet operator,
I want to manually advance any subscriber's status with a documented reason, and view the full audit trail for any account or subscriber,
So that I can handle edge cases with full accountability and review all engine activity for compliance.

**Acceptance Criteria:**

**Given** the operator selects a subscriber in the console
**When** they click "Advance status" and select the target status
**Then** the subscriber's status is updated (with reason recorded in audit log) for edge cases the polling detection misses (FR42)
**And** `write_audit_event(subscriber, actor="operator", action="status_advanced", outcome="success", metadata={from: "active", to: "passive_churn", reason: "..."})` is called
**And** a reason is required — the form does not submit without one

**Given** the audit log viewer in the operator console
**When** I filter by account or by subscriber
**Then** I see the complete append-only audit log: every email sent, status change, manual override, and system event — with timestamp, actor, action, and outcome (FR43, FR44)
**And** no record in the audit log can be modified or deleted through any application interface (NFR-R3)
**And** audit logs are retained for 36 months (NFR-D2)

**Given** the operator views the dead-letter log
**When** failed Celery tasks are listed
**Then** each entry shows: task name, account ID, error string, timestamp, and retry count
**And** the operator can trigger a manual re-queue for eligible failed tasks (NFR-R5)
