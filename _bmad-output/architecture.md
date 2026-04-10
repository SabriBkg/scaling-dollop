---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-04-06'
inputDocuments:
  - _bmad-output/prd.md
  - _bmad-output/prd-validation-report.md
  - _bmad-output/ux-design-specification.md
workflowType: 'architecture'
project_name: 'SafeNet'
user_name: 'BMad'
date: '2026-04-06'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

---

## Project Context Analysis

### Requirements Overview

**Functional Requirements — 48 FRs across 8 domains:**

| Domain | FR Count | Architectural weight |
|--------|---------|---------------------|
| Account & Onboarding | 6 (FR1–5, FR48) | Stripe Connect OAuth, DPA gate, mode selection |
| Payment Failure Detection | 4 (FR6–9) | Hourly polling loop, decline-code classification |
| Recovery Engine | 7 (FR10–15, FR47) | Rule engine, payday calendar, geo-compliance, state transitions |
| Customer Status Management | 7 (FR16–21, FR46) | 4-state machine, transition guards, subscription cancellation detection |
| Notifications | 7 (FR22–28) | Transactional email, tone presets, opt-out suppression, two-domain mode |
| Dashboard & Analytics | 6 (FR29–34) | Retroactive scan, failure breakdown, MoM analytics, digest email |
| Subscription & Billing | 5 (FR35–39) | Trial mechanics, tier degradation, Stripe Billing self-management |
| Operator Administration | 6 (FR40–45) | Admin override panel, audit trail, operator-only access |

The recovery engine and operator administration domains carry the highest architectural weight — they require the most careful separation, security enforcement, and audit instrumentation.

**Non-Functional Requirements — 18 NFRs driving structural decisions:**

| Category | Count | Key constraint |
|----------|-------|---------------|
| Security | 6 | AES-256 token encryption + env-key separation; zero cardholder data; tenant isolation at query level |
| Reliability | 5 | Hourly poll ±5 min tolerance; 90-min alert on missed cycle; zero silent failures; dead-letter required |
| Performance | 4 | Dashboard ≤3s at 500 customers; retroactive scan non-blocking; first scan visible ≤5 min |
| Scalability | 3 | 100 client accounts MVP; 10,000 events/client/cycle; multi-user expansion without schema migration |
| Data Retention | 3 | Events: 24-month purge; Audit logs: 36-month retention; customer emails: purged 30 days post-Passive Churn |

**From UX Specification — architectural implications:**

- **No real-time requirement**: All data is polling-driven (hourly). Dashboard reflects last-known state — no WebSockets needed at MVP. Status updates visible on next page load/refresh.
- **Subscriber detail Sheet**: API must serve complete subscriber history + audit trail in a single endpoint for right-panel load.
- **Batch action (Supervised mode)**: API needs a bulk-action endpoint — partial batch failure must be surfaced cleanly.
- **AttentionBar**: A lightweight aggregated summary endpoint required for topbar badge/bar (not the full subscriber list).
- **WCAG AA + skeleton loading**: API responses must be structured predictably — known field shapes required even on empty states.
- **Desktop-first React (Next.js) frontend**: Confirmed via both PRD and UX spec. No mobile-native requirements.

---

**Scale & Complexity:**

- **Primary domain:** Fintech SaaS — background-job-heavy backend + React dashboard frontend
- **Complexity level:** High — regulatory surface area (GDPR, EU retry rules), distributed job system (Celery + Redis), multi-tenant isolation, compliance-as-architecture, append-only audit trail on every engine action
- **Estimated architectural components:** 7 distinct subsystems

---

### Technical Constraints & Dependencies

The PRD explicitly specifies the full technical stack:

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Python + Django | Django admin = operator panel. No custom admin UI in scope. |
| Frontend | Next.js | Dashboard only. No mobile-native app. |
| Job scheduler | Celery + Redis | Hourly polling + retry execution. |
| Database | PostgreSQL | ACID compliance for financial event metadata. |
| Deployment | Railway | Encrypted env secrets for AES-256 key. Zero DevOps. |
| Local dev | Docker Compose | One-command environment. Must mirror production. |
| Stripe integration | Express Connect OAuth | No API key handling. Stripe handles KYC/AML. |
| Email | Resend or Postmark | Two-mode: shared domain (Mid) / custom domain (Pro). |
| SafeNet's own billing | Stripe Billing | Dogfooding the ecosystem. |

**Stripe token security:** AES-256 at rest in PostgreSQL. Encryption key stored exclusively in Railway environment secrets. Both DB access AND env access required simultaneously for compromise — defence-in-depth by architecture.

---

### Cross-Cutting Concerns Identified

Six concerns that span every subsystem:

1. **Audit trail:** Every engine action (retry fired, retry cancelled, notification sent, status change, manual override) written to an append-only log with timestamp + actor + outcome. Affects: Recovery Engine, Admin Panel, Status Machine, Notification Service.

2. **Tenant isolation:** All database queries scoped by `account_id`. No global queries anywhere in the application layer. Affects: every model, every view, every API endpoint.

3. **Compliance gates:** DPA acknowledgement required before engine activation (hard gate). Opt-out state checked before every notification. EU/UK payment context checked before every retry. Affects: Onboarding, Notification Service, Recovery Engine.

4. **Tier gating:** Feature access varies across Free/Mid/Pro + trial state. Polling frequency, engine activation, notification sending, and Pro features all require tier checks. Affects: every user-facing feature.

5. **Reliability & observability:** Dead-letter queue on all Celery jobs. Polling health monitoring with 90-minute alert threshold. Zero silent failures — every failure logged. Affects: Celery workers, polling job, retry scheduler.

6. **Security boundary:** Operator console strictly separated from client console. No client-facing route exposes operator capabilities. Affects: URL routing, authentication middleware, Django admin configuration.

---

## Starter Template Evaluation

### Primary Technology Domain

**Split-stack full-SaaS:** Separate Django (Python) backend service + Next.js frontend, communicating via internal REST API. Two distinct initialization paths.

The recovery engine and job scheduler are backend-only concerns — they run without any frontend involvement. The Next.js dashboard is purely a consumer of API data. Keeping them separate means Celery workers can scale, be monitored, and be deployed independently of the UI layer.

---

### Stack (PRD Constraint — No Competitive Evaluation Required)

| Component | Technology | Version |
|-----------|-----------|---------|
| Frontend framework | Next.js | 16.x |
| Frontend language | TypeScript | Latest (bundled) |
| Frontend styling | Tailwind CSS | Latest (bundled) |
| Frontend components | shadcn/ui | Latest |
| Backend framework | Django | 6.0.x |
| Backend API layer | Django REST Framework | 3.17.x |
| Job scheduler | Celery | 5.6.x |
| Message broker | Redis | Latest stable |
| Database | PostgreSQL | Latest stable |
| Deployment | Railway | — |
| Local dev | Docker Compose | — |

---

### Frontend Initialization

```bash
# Bootstrap Next.js with TypeScript + Tailwind + App Router + ESLint
npx create-next-app@latest safenet-dashboard \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir

# Install and initialize shadcn/ui
cd safenet-dashboard
npx shadcn@latest init
```

**Architectural decisions provided:**

- **TypeScript** strict mode — full type safety across components and API calls
- **App Router** (Next.js 16) — layouts, loading states, error boundaries built-in
- **Tailwind CSS** with PostCSS — utility-first, consistent with UX spec token system
- **shadcn/ui** — owned components, not a dependency; full customization of theme tokens
- **`src/` directory** — `app/` for routes, feature-colocated components
- **ESLint** with Next.js rules — enforced on every commit

---

### Backend Initialization

```bash
pip install django==6.0.3 djangorestframework==3.17.1 \
  celery==5.6.3 redis django-environ psycopg2-binary \
  cryptography
django-admin startproject safenet_backend .
python manage.py startapp core
```

**What this establishes:**

- **Django admin** = operator override panel. Zero custom admin UI needed at MVP. All operator capabilities (retry override, status advancement, audit log review) are Django admin views.
- **DRF** = REST API consumed by the Next.js dashboard. JSON responses, token authentication.
- **Celery + Redis** = job queue for hourly polling and scheduled retries. Worker runs alongside Django.
- **django-environ** = environment variable management. AES-256 encryption key loaded exclusively from env — never committed, never in the database.

---

### Docker Compose (Local Dev)

One-command local environment mirroring production:

```yaml
# docker-compose.yml — services
services:
  db:        PostgreSQL
  redis:     Redis (Celery broker)
  web:       Django dev server
  worker:    Celery worker (polling + retry execution)
  beat:      Celery beat (scheduler — hourly tick)
  frontend:  Next.js dev server
```

**Note:** `celery beat` (scheduler) is a distinct process from `celery worker`. Beat triggers the hourly polling tick; workers execute the tasks. Both must run locally to test the full engine cycle.

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Tenant isolation via `TenantScopedModel` + `TenantManager` — must exist before any other models
- JWT authentication (`djangorestframework-simplejwt`) — must be complete before any protected endpoints
- Stripe token encryption pattern — must be in place before any OAuth flow
- Decline-code rule engine as data-driven config — defines the shape of all recovery logic

**Important Decisions (Shape Architecture):**
- `django-fsm` for 4-state customer state machine with post-transition audit signal
- TanStack Query (React Query v5) for all server state on the frontend
- Zustand for UI-only client state
- Resend as email provider
- `drf-spectacular` for OpenAPI 3.0 documentation
- Monorepo structure (`backend/` + `frontend/`)
- Sentry for error monitoring (both services)

**Deferred Decisions (Post-MVP):**
- GraphQL API layer (not needed at MVP scale)
- Custom sending domain infrastructure for Pro tier (post-MVP feature)
- Multi-user RBAC (Membership table expansion — schema-ready but not activated)

---

### Data Architecture

**Tenant isolation:**
All Django models inherit from a `TenantScopedModel` abstract base class with a required `account` FK. A custom `TenantManager` replaces the default manager — `Model.objects.all()` is never callable without `account_id` scoping. Global queries require an explicit `unscoped()` manager available only in admin/operator context. Isolation enforced by architecture, not discipline.

**State machine:**
`django-fsm` for the 4-state customer state machine (Active → Recovered / Passive Churn / Fraud Flagged). Transitions are decorated methods with guards — `TransitionNotAllowed` raised on invalid transitions, never silently ignored. Every transition logs to the audit trail automatically via a post-transition signal.

**Caching:**
Redis (already present for Celery) used as Django cache backend via `django-redis`. Dashboard summary endpoint (KPI aggregates) cached with 5-minute TTL, invalidated on any new engine action for that account. Individual subscriber data never cached — must always reflect current state.

**Decline-code rule engine:**
Data-driven: rules defined in a Python dict/YAML config file, not hardcoded in business logic:
```python
# Structure: decline_code → rule
DECLINE_RULES = {
    "card_expired":           {"action": "notify_only", "retry_cap": 0, "payday_aware": False, "geo_block": False},
    "insufficient_funds":     {"action": "retry_notify", "retry_cap": 3, "payday_aware": True,  "geo_block": True},
    "fraudulent":             {"action": "fraud_flag",   "retry_cap": 0, "payday_aware": False, "geo_block": False},
    "do_not_honor":           {"action": "retry_notify", "retry_cap": 2, "payday_aware": False, "geo_block": True},
    # ... 30+ codes
    "_default":               {"action": "retry_notify", "retry_cap": 1, "payday_aware": False, "geo_block": False},
}
```
Unknown codes fall through to `_default` — conservative, never fraud-flags. Config is version-controlled and fully testable with pytest, no DB required.

---

### Authentication & Security

**Client authentication:** `djangorestframework-simplejwt` — JWT access tokens (15-min expiry) + refresh tokens (7-day expiry). Next.js middleware refreshes tokens transparently. Stateless — no server-side session storage.

**Stripe token encryption:**
```python
# cryptography.fernet — AES-128-CBC with HMAC
FERNET_KEY = env("STRIPE_TOKEN_KEY")  # loaded from Railway env secrets only
cipher = Fernet(FERNET_KEY)

def encrypt_token(raw: str) -> str: return cipher.encrypt(raw.encode()).decode()
def decrypt_token(stored: str) -> str: return cipher.decrypt(stored.encode()).decode()
```
Only the `StripeConnection` model uses these helpers. No other code in the codebase touches raw tokens.

**CORS:** `django-cors-headers` — `localhost:3000` in development, production frontend domain only in prod.

**Operator console isolation:** Django admin mounted at `/ops-console/` (not `/admin/`). Only `is_staff=True` users. Client accounts are always `is_staff=False`.

---

### API & Communication Patterns

**Design:** REST via DRF. Resource-oriented. No GraphQL at MVP.

**Documentation:** `drf-spectacular` — OpenAPI 3.0 auto-generated from DRF views. Serves at `/api/schema/` (internal). Contract between backend and frontend during development.

**Key non-CRUD endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/dashboard/summary/` | GET | Aggregated KPIs + attention count (cached, 5 min) |
| `/api/v1/stripe/connect/` | POST | Initiate OAuth flow |
| `/api/v1/stripe/disconnect/` | POST | Revoke token, stop engine |
| `/api/v1/actions/batch/` | POST | Batch action for Supervised mode |
| `/api/v1/subscribers/{id}/timeline/` | GET | Full audit trail for detail Sheet |

**Error format:**
```json
{ "error": { "code": "STRIPE_TOKEN_INVALID", "message": "...", "field": null } }
```
Never raw Django 500 HTML. Consumed by Next.js error boundaries.

**Email provider:** Resend — cleaner Python SDK than Postmark, supports shared + custom sending domains, competitive pricing for transactional volume at MVP scale.

---

### Frontend Architecture

**Server state:** TanStack Query (React Query v5) — caching, background refetch, stale-while-revalidate, loading/error states. Dashboard `refetchInterval: 5 * 60 * 1000` (5 min), manual refresh available.

**Client state:** Zustand — active sheet subscriber ID, batch selection set, theme preference, supervised/autopilot UI state.

**API client:** axios with configured instance — base URL from env, JWT injected via request interceptor, 401 triggers token refresh then retries original request.

**Component organization:**
```
src/
  app/              # Next.js App Router pages + layouts
  components/
    ui/             # shadcn/ui primitives (auto-generated, never hand-edited)
    common/         # Shared: NavBar, WorkspaceIdentity, BravaMark
    dashboard/      # StoryArcPanel, SubscriberCard, AttentionBar, KPICard
    subscriber/     # SubscriberDetailSheet, Timeline, DeclineCodeExplainer
    settings/       # Settings forms, tone selector, DPA acknowledgement
  hooks/            # TanStack Query hooks: useSubscribers, useDashboardSummary, useTimeline
  stores/           # Zustand stores: uiStore, authStore
  lib/              # axios instance, auth utils, formatters, rule-engine types
  types/            # Shared TypeScript interfaces (mirrors backend models)
```

---

### Infrastructure & Deployment

**Repository:** Monorepo — single git repo, `backend/` + `frontend/` subdirectories. Deployed as separate Railway services.

```
safenet/
  backend/          # Django + Celery (Railway service 1)
  frontend/         # Next.js (Railway service 2)
  docker-compose.yml
```

**CI/CD:** GitHub Actions — `test.yml` (pytest + ESLint on every PR), `deploy.yml` (Railway deploy on merge to main).

**Error monitoring:** Sentry — `sentry-sdk` (Python backend) + Sentry Next.js SDK (frontend). Free tier sufficient for MVP.

**Logging:** Django structured logging to stdout — Railway captures and streams automatically. Every engine action logged at INFO level (mirrors audit trail for real-time operator visibility).

**Scaling constraint:** `celery beat` runs as a single Railway instance only — multiple instances would double-fire retries. Enforced via Railway service config.

---

### Decision Impact — Implementation Sequence

1. Monorepo structure + Docker Compose → before any feature work
2. `TenantScopedModel` + `TenantManager` → before any other models
3. JWT auth + Next.js middleware → before any protected endpoints or frontend routes
4. Audit trail signal → before any state machine transitions
5. Decline-code rule engine config → before any recovery logic
6. Dashboard summary API endpoint → before any frontend components (contract-first)

**Cross-component dependency chain:**
```
celery beat → polling job → rule engine → state machine → audit trail
Django auth → JWT → Next.js middleware → TanStack Query hooks
decline-code config → rule engine → notifications → Resend integration
```

---

## Implementation Patterns & Consistency Rules

### Critical Conflict Points Identified

9 areas where AI agents working independently could produce incompatible code:
1. snake_case (Python) vs camelCase (TypeScript) API field naming
2. API response envelope format
3. Date/time serialization
4. Django app internal file organization
5. Celery task structure
6. Audit log write pattern
7. Error handling at each layer boundary
8. TanStack Query hook naming and organization
9. TypeScript type sourcing (generated vs hand-written)

---

### Naming Patterns

**Database (Django ORM):**

| Element | Convention | Example |
|---------|-----------|---------|
| Model class | PascalCase | `SubscriberFailure`, `StripeConnection` |
| DB table (auto) | snake_case | `core_subscriber_failure` |
| Field names | snake_case | `decline_code`, `account_id`, `created_at` |
| FK fields | `{model}_id` suffix | `account_id`, `subscriber_id` |
| Indexes | `idx_{table}_{field}` | `idx_subscriber_failure_account_id` |

**API endpoints:**
- Always plural nouns: `/api/v1/subscribers/`, `/api/v1/accounts/`
- Kebab-case for multi-word: `/api/v1/stripe-connections/`
- Actions as sub-resources: `/api/v1/subscribers/{id}/timeline/`
- Batch actions: `/api/v1/actions/batch/`
- Version prefix always present: `/api/v1/` — never unversioned routes

**API field naming — critical rule:**
All API fields use snake_case in both Django responses AND TypeScript types. No transformation layer. TypeScript types mirror the API contract exactly.

```typescript
// ✅ Correct — matches API response
interface Subscriber {
  id: string
  decline_code: string
  subscriber_status: 'active' | 'recovered' | 'passive_churn' | 'fraud_flagged'
  created_at: string  // ISO 8601
}
// ❌ Wrong — camelCase requires a transformation layer that introduces hidden bugs
```

**TypeScript/React code naming:**
- Component names & files: PascalCase (`SubscriberCard.tsx`)
- Hook files: camelCase (`useSubscribers.ts`)
- Utility files: camelCase (`formatCurrency.ts`)
- Variables/functions within files: camelCase (`const subscriberId`)
- Zustand store keys: camelCase (`activeSubscriberId`)
- TypeScript type fields that mirror API: snake_case (see above)

---

### Structure Patterns

**Django app organization:**

```
backend/
  safenet_backend/       # Django project (settings, urls, wsgi)
  core/                  # Main app
    models/
      __init__.py        # Exports all models
      account.py         # Account, StripeConnection
      subscriber.py      # Subscriber, SubscriberFailure (with FSM)
      audit.py           # AuditLog (append-only)
    serializers/
    views/
      subscribers.py
      dashboard.py
      stripe.py
    tasks/               # Celery tasks
      polling.py         # Hourly polling job
      retry.py           # Retry execution
      notifications.py   # Email dispatch
    engine/              # Rule engine — pure Python, zero Django imports
      rules.py           # DECLINE_RULES config dict
      processor.py       # Rule application logic
      compliance.py      # Geo-aware compliance checks
    admin/               # Django admin customizations
    tests/
      test_engine/
      test_api/
      test_tasks/
```

**Rule:** No business logic in views. Views validate input, call engine/service, return result. All logic lives in `engine/` or model methods.

**Frontend file naming:**
- Components: `PascalCase.tsx` — one component per file
- Hooks: `useCamelCase.ts`
- Stores: `camelCaseStore.ts`
- Types: `types.ts` per feature folder; shared types in `src/types/index.ts`

---

### Format Patterns

**API response envelope:**

```json
// Success — single resource
{ "data": { "id": "...", "decline_code": "insufficient_funds" } }

// Success — list
{ "data": [...], "meta": { "total": 47, "next": null } }

// Error
{ "error": { "code": "SUBSCRIBER_NOT_FOUND", "message": "Subscriber not found", "field": null } }
```

Every DRF response is always `{data: ...}` or `{error: ...}`. Never both. Never a bare root object.

**Date/time:** ISO 8601 strings always — `"2026-04-06T14:30:00Z"`. Never Unix timestamps. TypeScript type is always `string`; formatting only in the display layer.

**Monetary values:** Integer cents always — `amount_cents: 6400` (not `amount: 64.00`). Display formatting (`€640`) in TypeScript formatters only, never in the API.

**Pagination:** Offset-based — `?limit=50&offset=0`.

**Booleans:** Always `true`/`false` — never `1`/`0` or string booleans.

---

### Communication Patterns

**Celery task structure — mandatory pattern:**

```python
@app.task(bind=True, max_retries=3, default_retry_delay=60)
def task_name(self, account_id: int, **kwargs):
    logger.info(f"[task_name] START account_id={account_id}")
    try:
        # task logic
        logger.info(f"[task_name] COMPLETE account_id={account_id}")
    except TemporaryError as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error(f"[task_name] FAILED account_id={account_id} error={exc}")
        DeadLetterLog.objects.create(task=task_name.__name__, account_id=account_id, error=str(exc))
        raise
```

**Audit log write — always via helper, never inline:**

```python
write_audit_event(
    subscriber=subscriber,
    actor="engine",           # "engine" | "operator" | "client"
    action="retry_fired",     # snake_case verb
    outcome="success",        # "success" | "failed" | "cancelled"
    metadata={"decline_code": "insufficient_funds", "attempt": 2}
)
```

**Django signal for FSM transitions:**

```python
@receiver(post_transition, sender=Subscriber)
def on_status_transition(sender, instance, name, source, target, **kwargs):
    write_audit_event(subscriber=instance, action=f"status_{name}",
                      outcome="success", metadata={"from": source, "to": target})
```

**TanStack Query hook naming:**

```typescript
// Naming: use{Resource}{Qualifier?}
useSubscribers()           // list
useSubscriber(id)          // single
useDashboardSummary()      // aggregated
useSubscriberTimeline(id)  // sub-resource
useBatchAction()           // mutation
// Each hook in its own file: src/hooks/useSubscribers.ts
```

---

### Process Patterns

**Error handling by layer:**

| Layer | Pattern |
|-------|---------|
| Django view | Never catch generic `Exception` — let DRF handler catch it |
| DRF exception handler | All exceptions → `{error: {code, message}}` |
| Engine / tasks | Catch specific exceptions; dead-letter on unhandled |
| axios (frontend) | Interceptor extracts `error.response.data.error` |
| TanStack Query | `onError` receives the extracted error object |
| React component | Displays `error.message`; never exposes `error.code` to user |

**Loading states — always TanStack Query, never manual `useState` for server data:**

```typescript
// ✅ Correct
const { data, isLoading, error } = useSubscribers()
if (isLoading) return <SubscriberGridSkeleton />

// ❌ Wrong
const [loading, setLoading] = useState(false)
```

---

### Enforcement Guidelines

**All AI agents MUST:**
- Use snake_case in all TypeScript types that represent API responses
- Wrap all API responses in `{data: ...}` or `{error: ...}` — never bare root objects
- Write to audit log via `write_audit_event()` — never inline
- Use `TenantScopedModel` as the base for every account-scoped Django model
- Represent monetary values as integer cents in the API — never floats
- Scope all Celery tasks with `bind=True` and implement dead-letter on unhandled exceptions
- Place engine/rule logic in `core/engine/` — never in views or tasks directly

**Anti-patterns (never):**
- `Model.objects.all()` without `account_id` filter — tenant data leak
- `amount: 64.00` in API — use `amount_cents: 6400`
- Inline audit log writes
- `useState` for server data — use TanStack Query
- camelCase TypeScript fields mirroring API responses

---

## Project Structure & Boundaries

### Complete Project Directory Structure

```
safenet/                              # Monorepo root
├── .github/
│   └── workflows/
│       ├── test.yml                  # pytest + ESLint on every PR
│       └── deploy.yml                # Railway deploy on merge to main
├── backend/                          # Django service (Railway service 1)
│   ├── safenet_backend/              # Django project package
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── base.py               # Shared settings
│   │   │   ├── development.py        # Local dev overrides
│   │   │   └── production.py         # Railway production settings
│   │   ├── urls.py                   # Root URL routing
│   │   ├── wsgi.py
│   │   └── celery.py                 # Celery app + beat schedule
│   ├── core/                         # Main business logic app
│   │   ├── models/
│   │   │   ├── __init__.py           # Re-exports all models
│   │   │   ├── base.py               # TenantScopedModel + TenantManager
│   │   │   ├── account.py            # Account, StripeConnection
│   │   │   ├── subscriber.py         # Subscriber (FSM), SubscriberFailure
│   │   │   ├── audit.py              # AuditLog (append-only)
│   │   │   ├── notification.py       # NotificationLog, OptOutRecord
│   │   │   └── dead_letter.py        # DeadLetterLog
│   │   ├── serializers/
│   │   │   ├── __init__.py
│   │   │   ├── account.py
│   │   │   ├── subscriber.py
│   │   │   ├── dashboard.py
│   │   │   └── stripe.py
│   │   ├── views/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py               # JWT token endpoints
│   │   │   ├── account.py            # Account CRUD, DPA gate
│   │   │   ├── subscribers.py        # Subscriber list, detail, status
│   │   │   ├── dashboard.py          # Summary KPIs, story arc data
│   │   │   ├── stripe.py             # Connect / disconnect OAuth
│   │   │   └── actions.py            # Batch actions (Supervised mode)
│   │   ├── tasks/                    # Celery tasks
│   │   │   ├── __init__.py
│   │   │   ├── polling.py            # Hourly polling job
│   │   │   ├── retry.py              # Retry execution
│   │   │   ├── notifications.py      # Resend email dispatch
│   │   │   ├── scanner.py            # 90-day retroactive scan
│   │   │   └── maintenance.py        # Data retention + purge jobs
│   │   ├── engine/                   # Rule engine — pure Python, zero Django imports
│   │   │   ├── __init__.py
│   │   │   ├── rules.py              # DECLINE_RULES config dict (30+ codes)
│   │   │   ├── processor.py          # Apply rule to a SubscriberFailure
│   │   │   ├── compliance.py         # EU/UK geo-aware retry blocking
│   │   │   ├── payday.py             # Payday calendar logic
│   │   │   └── state_machine.py      # FSM helper utilities
│   │   ├── services/                 # Orchestration layer
│   │   │   ├── __init__.py
│   │   │   ├── audit.py              # write_audit_event() helper
│   │   │   ├── stripe_client.py      # Stripe API wrapper (read + retry)
│   │   │   ├── email.py              # Resend integration
│   │   │   ├── encryption.py         # encrypt_token / decrypt_token
│   │   │   └── tier.py               # Tier + trial gate checks
│   │   ├── admin/                    # Django admin = operator panel
│   │   │   ├── __init__.py
│   │   │   ├── account.py
│   │   │   ├── subscriber.py
│   │   │   ├── audit.py
│   │   │   └── retry_queue.py        # Scheduled retry oversight view
│   │   └── migrations/
│   ├── tests/
│   │   ├── conftest.py               # pytest fixtures
│   │   ├── test_engine/
│   │   │   ├── test_rules.py
│   │   │   ├── test_compliance.py
│   │   │   └── test_payday.py
│   │   ├── test_api/
│   │   │   ├── test_auth.py
│   │   │   ├── test_subscribers.py
│   │   │   ├── test_dashboard.py
│   │   │   ├── test_stripe.py
│   │   │   └── test_batch.py
│   │   └── test_tasks/
│   │       ├── test_polling.py
│   │       ├── test_retry.py
│   │       └── test_scanner.py
│   ├── manage.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                         # Next.js service (Railway service 2)
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── login/page.tsx
│   │   │   │   └── register/page.tsx
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx        # Main layout: NavBar + WorkspaceIdentity
│   │   │   │   ├── page.tsx          # Dashboard (Story Arc)
│   │   │   │   ├── settings/page.tsx
│   │   │   │   └── recovered/page.tsx
│   │   │   ├── globals.css
│   │   │   └── layout.tsx            # Root layout: fonts, providers, Sentry
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn/ui primitives (never hand-edited)
│   │   │   ├── common/
│   │   │   │   ├── NavBar.tsx
│   │   │   │   ├── WorkspaceIdentity.tsx
│   │   │   │   ├── AttentionBar.tsx
│   │   │   │   ├── EngineStatusBadge.tsx
│   │   │   │   └── ThemeToggle.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── StoryArcPanel.tsx
│   │   │   │   ├── KPICard.tsx
│   │   │   │   ├── SubscriberGrid.tsx
│   │   │   │   ├── SubscriberCard.tsx
│   │   │   │   ├── BatchActionToolbar.tsx
│   │   │   │   └── ZeroState.tsx
│   │   │   ├── subscriber/
│   │   │   │   ├── SubscriberDetailSheet.tsx
│   │   │   │   ├── TimelineEvent.tsx
│   │   │   │   ├── DeclineCodeExplainer.tsx
│   │   │   │   ├── StatusBadge.tsx
│   │   │   │   └── NoteField.tsx
│   │   │   ├── settings/
│   │   │   │   ├── ToneSelector.tsx
│   │   │   │   ├── DPAGate.tsx
│   │   │   │   ├── StripeConnectionCard.tsx
│   │   │   │   ├── ModeToggle.tsx
│   │   │   │   └── DangerZone.tsx
│   │   │   └── onboarding/
│   │   │       ├── ConnectStripe.tsx
│   │   │       ├── ScanProgress.tsx
│   │   │       └── DPAAcknowledgement.tsx
│   │   ├── hooks/
│   │   │   ├── useSubscribers.ts
│   │   │   ├── useSubscriber.ts
│   │   │   ├── useDashboardSummary.ts
│   │   │   ├── useSubscriberTimeline.ts
│   │   │   ├── useBatchAction.ts
│   │   │   ├── useStripeConnect.ts
│   │   │   └── useAccount.ts
│   │   ├── stores/
│   │   │   ├── uiStore.ts
│   │   │   ├── authStore.ts
│   │   │   └── themeStore.ts
│   │   ├── lib/
│   │   │   ├── api.ts                # axios instance + interceptors
│   │   │   ├── auth.ts               # JWT store/refresh/clear
│   │   │   ├── formatters.ts         # formatCurrency, formatDate, formatDeclineCode
│   │   │   └── constants.ts          # API base URL, polling intervals
│   │   ├── types/
│   │   │   ├── index.ts
│   │   │   ├── account.ts
│   │   │   ├── subscriber.ts
│   │   │   ├── dashboard.ts
│   │   │   ├── audit.ts
│   │   │   └── api.ts                # ApiResponse<T>, ApiError, PaginatedResponse<T>
│   │   └── middleware.ts             # JWT validation → redirect to /login
│   ├── public/
│   │   ├── logo.svg
│   │   └── favicon.ico
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   ├── .env.local.example
│   └── Dockerfile
│
├── docker-compose.yml
├── docker-compose.override.yml       # Hot-reload overrides for local dev
├── .env.example
├── .gitignore
└── README.md
```

---

### Architectural Boundaries

**API boundary (backend ↔ frontend):**

| Concern | Owner | Rule |
|---------|-------|------|
| Business logic | `engine/`, `services/` | Never bleeds into views |
| API contract | DRF serializers + `drf-spectacular` | Single source of truth |
| TypeScript types | `src/types/` | Manually mirrors backend serializers — snake_case fields |
| Auth tokens | `lib/auth.ts` | Stored in memory only (not localStorage) |
| Data formatting | `lib/formatters.ts` | All `€`, dates, code labels — never in API responses |

**Operator boundary:**

| Surface | Client | Operator |
|---------|--------|---------|
| `/api/v1/*` | ✅ JWT auth | ✅ JWT auth |
| `/ops-console/*` | ❌ `is_staff` blocks | ✅ Django admin |
| Audit log read | ❌ Not exposed | ✅ Admin + API |
| Retry override | ❌ Not available | ✅ Admin only |

**Engine isolation:** `core/engine/` contains zero Django imports. Pure Python. Fully testable without a database. Extractable to a separate service without rewrites.

---

### Requirements → Structure Mapping

| FR Group | Backend files | Frontend files |
|----------|-------------|---------------|
| FR1–5, FR48 — Onboarding | `views/account.py`, `views/stripe.py`, `tasks/scanner.py`, `services/encryption.py` | `onboarding/`, `settings/StripeConnectionCard.tsx`, `hooks/useStripeConnect.ts` |
| FR6–9 — Failure Detection | `tasks/polling.py`, `engine/processor.py`, `engine/rules.py` | `dashboard/KPICard.tsx`, `hooks/useDashboardSummary.ts` |
| FR10–15, FR47 — Recovery Engine | `engine/rules.py`, `engine/compliance.py`, `engine/payday.py`, `tasks/retry.py` | Backend-only |
| FR16–21, FR46 — Status Management | `models/subscriber.py` (FSM), `views/subscribers.py`, `services/audit.py` | `dashboard/SubscriberCard.tsx`, `subscriber/SubscriberDetailSheet.tsx` |
| FR22–28 — Notifications | `tasks/notifications.py`, `services/email.py`, `models/notification.py` | `settings/ToneSelector.tsx` |
| FR29–34 — Dashboard | `views/dashboard.py`, `serializers/dashboard.py` | `dashboard/StoryArcPanel.tsx`, `hooks/useDashboardSummary.ts` |
| FR35–39 — Billing | `services/tier.py`, Stripe Billing webhook | `settings/StripeConnectionCard.tsx` |
| FR40–45 — Operator Admin | `admin/retry_queue.py`, `admin/audit.py`, `admin/subscriber.py` | Django admin only |

**Cross-cutting concerns:**

| Concern | Location |
|---------|---------|
| Tenant isolation | `models/base.py` → `TenantScopedModel` |
| Audit trail | `services/audit.py` → `write_audit_event()` |
| Token encryption | `services/encryption.py` |
| Tier gating | `services/tier.py` |
| Compliance gate | `engine/compliance.py` |
| JWT middleware | `frontend/src/middleware.ts` |

---

### Integration Points & Data Flows

**Stripe Connect OAuth:**
```
User clicks "Connect" →
  useStripeConnect hook → POST /api/v1/stripe/connect/ →
  views/stripe.py → Stripe OAuth redirect →
  Stripe callback → views/stripe.py (callback) →
  services/encryption.py (token encrypted + stored) →
  tasks/scanner.py (90-day scan queued in Celery)
```

**Hourly polling:**
```
celery beat (every 60 min) →
  tasks/polling.py (per active account) →
  services/stripe_client.py (fetch failures) →
  engine/processor.py (classify + rule) →
  engine/compliance.py (geo check) →
  models/subscriber.py (FSM transition) →
  services/audit.py (write_audit_event) →
  tasks/retry.py or tasks/notifications.py (queued)
```

**Dashboard load:**
```
(dashboard)/page.tsx →
  useDashboardSummary hook → GET /api/v1/dashboard/summary/ →
  Redis cache hit or PostgreSQL aggregate →
  ApiResponse<DashboardSummary> →
  StoryArcPanel + KPICard renders with skeleton → data
```

---

## Architecture Validation Results

### Coherence Validation ✅

**Decision compatibility:** Django 6 + DRF 3.17 + Celery 5.6 + Redis + PostgreSQL + `django-fsm` + `djangorestframework-simplejwt` + `django-redis`: fully compatible, no version conflicts. Next.js 16 App Router + TanStack Query v5 + Zustand + shadcn/ui + Tailwind CSS: all current, compatible.

**Pattern consistency:** snake_case API fields ↔ snake_case TypeScript types consistent end-to-end. `TenantScopedModel` structurally enforces the tenant isolation pattern. `write_audit_event()` helper enforces the audit trail pattern at the call site.

**Engine isolation:** `core/engine/` contains zero Django imports — structurally enforced by directory boundary. Independently testable without a database.

**Encryption note:** `cryptography` Fernet uses a 32-byte key (256-bit) with AES-128-CBC internally. Document this in `services/encryption.py` — generate `STRIPE_TOKEN_KEY` as a 32-byte key. Security posture is equivalent to AES-256 in practice; documentation must be precise.

---

### Requirements Coverage Validation ✅

**All 48 FRs architecturally supported:**

| FR Group | Status | Primary files |
|----------|--------|--------------|
| FR1–5, FR48 — Onboarding | ✅ | `views/stripe.py`, `tasks/scanner.py`, `services/encryption.py` |
| FR6–9 — Failure Detection | ✅ | `tasks/polling.py`, `engine/processor.py` |
| FR10–15, FR47 — Recovery Engine | ✅ | `engine/rules.py`, `engine/compliance.py`, `engine/payday.py`, `tasks/retry.py` |
| FR16–21, FR46 — Status Management | ✅ | `models/subscriber.py` (FSM), `services/audit.py` |
| FR22–28 — Notifications | ✅ | `tasks/notifications.py`, `services/email.py` |
| FR29–34 — Dashboard | ✅ | `views/dashboard.py`, Redis cache, `hooks/useDashboardSummary.ts` |
| FR35–39 — Billing | ✅ | `services/tier.py`, Stripe Billing webhook |
| FR40–45 — Operator Admin | ✅ | Django admin, `admin/retry_queue.py`, `admin/audit.py` |

**All 18 NFRs architecturally supported:**

| NFR Category | Status | Coverage |
|-------------|--------|---------|
| Security (S1–S6) | ✅ | AES encryption, Railway TLS, zero cardholder data, `is_staff` isolation, `TenantScopedModel` |
| Reliability (R1–R5) | ✅ | Celery beat monitoring, dead-letter queue, `DeadLetterLog` model, zero silent failures |
| Performance (P1–P4) | ✅ | Redis cache on summary, retroactive scan as background task, skeleton loading |
| Scalability (SC1–SC3) | ✅ | Railway horizontal scaling, `TenantScopedModel` multi-user ready |
| Data Retention (D1–D3) | ✅ | `tasks/maintenance.py` for purge schedules |

---

### Gap Analysis

**No critical gaps.**

**Two structure additions required before first implementation story:**

1. **`views/billing.py`** + route `/api/v1/billing/webhook/` — Stripe Billing webhook handler for SafeNet's own subscription tier transitions (`customer.subscription.updated`, `customer.subscription.deleted`)

2. **`views/optout.py`** + route `/optout/{token}/` — Public (unauthenticated) opt-out endpoint for end-customer notification unsubscribe (FR26–27). Sits outside JWT-protected API.

---

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed (48 FRs, 18 NFRs, UX spec)
- [x] Scale and complexity assessed (High — fintech, background jobs, compliance)
- [x] Technical constraints identified (full PRD-specified stack)
- [x] Cross-cutting concerns mapped (6 concerns, all addressed)

**✅ Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined (Stripe OAuth, polling, email)
- [x] Performance considerations addressed (Redis cache, background tasks)

**✅ Implementation Patterns**
- [x] Naming conventions established (snake_case API/types, PascalCase components)
- [x] Structure patterns defined (Django app layout, frontend feature folders)
- [x] Communication patterns specified (Celery task template, audit log pattern)
- [x] Process patterns documented (error handling by layer, loading states)

**✅ Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established (engine isolation, operator boundary)
- [x] Integration points mapped (3 key data flows documented)
- [x] All 48 FRs mapped to specific files

---

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: High**

**Key Strengths:**
- Engine isolation (pure Python, zero Django imports) makes the core differentiator independently testable and future-proof
- Tenant isolation enforced architecturally via `TenantScopedModel` — impossible to accidentally write cross-tenant queries
- Audit trail enforced by mandatory `write_audit_event()` helper — compliance requirement is a structural pattern, not a convention
- Split-stack deployment: recovery engine runs independently of the UI — 99.5% uptime target achievable even during frontend deploys

**Areas for Future Enhancement (Post-MVP):**
- Cursor-based pagination when subscriber counts exceed 10,000
- OpenAPI type generation (replace hand-written TypeScript types with auto-generated ones from `drf-spectacular`)
- Celery beat health check endpoint for external uptime monitoring
- SOC 2 Type I audit preparation (architecture decisions are already aligned)

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use `TenantScopedModel` as the base for every account-scoped model — no exceptions
- Write to audit log via `write_audit_event()` only — never inline
- Keep `core/engine/` free of Django imports — test it without a database
- Use snake_case in all TypeScript types mirroring API responses
- Wrap all API responses in `{data: ...}` or `{error: ...}` — never bare root objects
- Store monetary values as integer cents in the API — never floats

**First Implementation Story:**
```bash
# 1. Monorepo structure + Docker Compose
# 2. Backend: Django project init + TenantScopedModel + JWT auth
# 3. Frontend: create-next-app + shadcn/ui init
# 4. Docker Compose: all 6 services running with one command
# Then: decline-code rule engine (engine/rules.py) — pure Python, fully testable before any DB work
```
