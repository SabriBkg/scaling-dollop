# Story 1.1: Monorepo Initialization, Docker Compose & CI/CD Pipeline

## Status: done

## Story

**As a developer,**
I want a monorepo with a one-command local dev environment and automated CI/CD,
So that both services can be built, tested, and deployed consistently from day one.

---

## Acceptance Criteria

**AC1 — Docker Compose one-command startup:**
- **Given** a fresh clone of the repository
- **When** I run `docker compose up`
- **Then** all 6 services start successfully: `db` (PostgreSQL), `redis`, `web` (Django dev server on :8000), `worker` (Celery worker), `beat` (Celery beat scheduler), `frontend` (Next.js on :3000)
- **And** each service communicates with its dependencies (Django ↔ PostgreSQL + Redis; Celery worker ↔ Redis)

**AC2 — CI test workflow:**
- **Given** a pull request is opened on GitHub
- **When** the `test.yml` GitHub Actions workflow runs
- **Then** it executes `pytest` against the Django backend and `eslint` against the Next.js frontend
- **And** the workflow fails (blocking merge) if any test or lint check fails

**AC3 — CI deploy workflow:**
- **Given** a commit is merged to `main`
- **When** the `deploy.yml` workflow runs
- **Then** the backend and frontend are deployed to their respective Railway services
- **And** the deploy fails visibly (not silently) if Railway rejects the deployment

**AC4 — Monorepo structure:**
- **Given** the monorepo structure
- **When** I inspect the root directory
- **Then** it contains `backend/` (Django), `frontend/` (Next.js), `docker-compose.yml`, and `.github/workflows/`
- **And** `celery beat` is configured as a single-instance Railway service — multiple instances are prevented to avoid double-firing retries

---

## Dev Agent Implementation Guide

### Critical Context

This is **Story 1.1 — the foundation**. Every subsequent story builds on what you create here. The choices you make (folder structure, service names, env var names) are load-bearing for all 22 remaining stories. Do not improvise — follow the specs exactly.

**No prior stories exist.** You are building from scratch.

---

### Exact Repository Structure to Create

```
safenet/                              # Monorepo root
├── .github/
│   └── workflows/
│       ├── test.yml                  # pytest + ESLint on every PR
│       └── deploy.yml                # Railway deploy on merge to main
├── backend/                          # Django service (Railway service 1)
│   ├── safenet_backend/
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── celery.py
│   ├── core/                         # Main Django app
│   │   ├── models/
│   │   │   └── __init__.py
│   │   ├── views/
│   │   ├── tasks/
│   │   ├── engine/
│   │   ├── admin/
│   │   └── tests/
│   │       └── conftest.py
│   ├── manage.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   ├── Dockerfile
│   └── .env.example
├── frontend/                         # Next.js service (Railway service 2)
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── login/page.tsx
│   │   │   │   └── register/page.tsx
│   │   │   ├── (dashboard)/
│   │   │   │   └── layout.tsx
│   │   │   ├── globals.css
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn/ui primitives (auto-generated, never hand-edit)
│   │   │   ├── common/
│   │   │   ├── dashboard/
│   │   │   ├── subscriber/
│   │   │   └── settings/
│   │   ├── hooks/
│   │   ├── stores/
│   │   ├── lib/
│   │   │   ├── api.ts                # axios instance + interceptors
│   │   │   ├── auth.ts
│   │   │   ├── formatters.ts
│   │   │   └── constants.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   └── middleware.ts             # JWT validation → redirect /login
│   ├── public/
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   ├── .env.local.example
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.override.yml       # Hot-reload overrides for local dev
├── .env.example
├── .gitignore
└── README.md
```

---

### Backend Bootstrap

**Exact pip packages (use these versions — no substitutions):**

```
django==6.0.3
djangorestframework==3.17.1
celery==5.6.3
redis
django-environ
psycopg2-binary
cryptography
djangorestframework-simplejwt
django-fsm
django-cors-headers
django-redis
drf-spectacular
sentry-sdk
```

**Initialize:**
```bash
cd backend
pip install -r requirements.txt
django-admin startproject safenet_backend .
python manage.py startapp core
```

**`backend/safenet_backend/celery.py` must exist** and configure:
- Celery app with `CELERY_BEAT_SCHEDULE` for hourly polling
- Auto-discover tasks from `core`
- Broker URL from `REDIS_URL` env var

**`backend/safenet_backend/__init__.py`** must import the Celery app so it initializes with Django.

**`backend/pytest.ini`** must configure:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = safenet_backend.settings.development
```

---

### Frontend Bootstrap

**Exact initialization:**
```bash
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir

cd frontend
npx shadcn@latest init
npm install @tanstack/react-query@5 zustand axios @sentry/nextjs
```

**TypeScript strict mode** must be enabled in `tsconfig.json` (`"strict": true`).

**`src/middleware.ts`** must be created as a stub — JWT validation and redirect to `/login`. Stories 1.2–1.4 will flesh it out; the file must exist here.

**`src/lib/api.ts`** must be created as a stub — axios instance with base URL from `NEXT_PUBLIC_API_URL` env var. Interceptors are wired in Story 1.2.

---

### Docker Compose — Exact Service Definitions

All 6 services are required. Use this structure:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: safenet
      POSTGRES_USER: safenet
      POSTGRES_PASSWORD: safenet
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U safenet"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  web:
    build: ./backend
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build: ./backend
    command: celery -A safenet_backend worker --loglevel=info
    volumes:
      - ./backend:/app
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
      db:
        condition: service_healthy

  beat:
    build: ./backend
    command: celery -A safenet_backend beat --loglevel=info
    volumes:
      - ./backend:/app
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
    # CRITICAL: In production (Railway), this service must run as exactly ONE instance.
    # Multiple beat instances double-fire retries. Enforce via Railway "replicas: 1" config.

  frontend:
    build: ./frontend
    command: npm run dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    env_file: .env
    depends_on:
      - web

volumes:
  postgres_data:
```

---

### GitHub Actions Workflows

**`.github/workflows/test.yml`** — runs on every PR:
```yaml
on:
  pull_request:
    branches: [main]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: safenet_test
          POSTGRES_USER: safenet
          POSTGRES_PASSWORD: safenet
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt -r requirements-dev.txt
        working-directory: backend
      - run: pytest
        working-directory: backend

  frontend-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
        working-directory: frontend
      - run: npm run lint
        working-directory: frontend
```

**`.github/workflows/deploy.yml`** — runs on merge to main:
```yaml
on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: railway/deploy@v1
        with:
          service: safenet-backend
          token: ${{ secrets.RAILWAY_TOKEN }}

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: railway/deploy@v1
        with:
          service: safenet-frontend
          token: ${{ secrets.RAILWAY_TOKEN }}
```

Note: Verify the exact Railway GitHub Action syntax/version against current Railway docs before finalizing. The `RAILWAY_TOKEN` secret must be added to the GitHub repo secrets.

---

### Environment Variables

**Root `.env.example`** (used by Docker Compose):
```bash
# Django
DJANGO_SETTINGS_MODULE=safenet_backend.settings.development
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://safenet:safenet@db:5432/safenet

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Encryption (placeholder — real key loaded from Railway secrets in prod)
STRIPE_TOKEN_KEY=placeholder-fernet-key-generate-with-Fernet.generate_key()

# Sentry (optional in dev)
SENTRY_DSN=
```

---

### Sentry Integration

**Backend:** Add to `base.py` settings:
```python
import sentry_sdk
sentry_sdk.init(dsn=env("SENTRY_DSN", default=""), traces_sample_rate=0.1)
```

**Frontend:** Initialize via `@sentry/nextjs` wizard or manual config in `next.config.js`. Stub is sufficient for Story 1.1 — full config in Story 1.4.

---

### Django Settings Split

**`base.py`** — shared settings (installed apps, middleware, DRF config stubs, Celery config, Sentry init)

**`development.py`** — inherits base; `DEBUG=True`, `ALLOWED_HOSTS=['*']`, SQLite or local PostgreSQL

**`production.py`** — inherits base; `DEBUG=False`, `ALLOWED_HOSTS` from env, `SECURE_SSL_REDIRECT=True`

Use `django-environ` for all env vars:
```python
import environ
env = environ.Env()
environ.Env.read_env()
```

---

### CORS Configuration

In `base.py`:
```python
INSTALLED_APPS += ['corsheaders']
MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware', ...rest]

# Development
CORS_ALLOWED_ORIGINS = ['http://localhost:3000']
# Production: set CORS_ALLOWED_ORIGINS from env
```

---

### Celery Single-Instance Constraint (Critical)

The `beat` service in Railway **must** be configured with `replicas: 1`. This is not a code constraint — it is a Railway service configuration constraint.

Document this in `README.md`:
> ⚠️ **celery beat must run as exactly one Railway instance.** Multiple instances cause double-firing of scheduled retries, which would trigger duplicate payment retries against Stripe — a serious financial bug.

---

### Testing Requirements

**What to test in Story 1.1:**
- Django server starts and returns 200 on `/api/health/` (create a minimal health check view)
- Celery worker can receive and execute a trivial test task
- All 6 Docker Compose services start without errors (`docker compose up --wait`)

**`backend/core/views/health.py`** — create a minimal health endpoint:
```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({"status": "ok"})
```

Wire it at `/api/health/` in `urls.py`.

**`backend/core/tests/test_health.py`** — at minimum:
```python
def test_health_check(client):
    response = client.get('/api/health/')
    assert response.status_code == 200
```

---

### What NOT to implement in Story 1.1

- No user models, no JWT auth setup → Story 1.2
- No `TenantScopedModel` → Story 1.2
- No Stripe token encryption → Story 1.2
- No decline-code rule engine → Story 1.3
- No frontend design tokens or state management → Story 1.4
- No dashboard UI → later epics

Keep `core/models/__init__.py` empty. Keep `core/tasks/` and `core/engine/` as empty directories with `__init__.py` placeholders only. Do not implement business logic — only infrastructure.

---

### Dependency Chain Context (Why This Matters)

All 22 remaining stories depend on the infrastructure you create here:
```
Story 1.1 (this) → Story 1.2 (TenantScopedModel + JWT) → Story 1.3 (Rule Engine) → Story 1.4 (Frontend)
                                                        ↓
                                              All Epic 2–6 stories
```

Getting Docker Compose service names, env var names, and folder structure wrong here causes cascading breakage across all stories.

---

## Out of Scope

- User authentication or authorization
- Any business logic or data models
- Frontend pages or components beyond skeleton/stubs
- Stripe integration
- Email integration

---

## Notes

- The project is named **SafeNet**. Use `safenet` consistently as the Django project name, Docker service prefix, and Railway service names.
- Python version: **3.12** (matches GitHub Actions config above)
- Node version: **20** (LTS)
- PostgreSQL version: **16**
- Redis version: **7**
- Railway is the deployment target — zero DevOps, Railway handles infra
- `drf-spectacular` is installed but only configured (serves `/api/schema/`) — Story 1.2 adds the actual DRF config

---

## Tasks/Subtasks

- [x] Task 1: Create root monorepo structure (`.gitignore`, `README.md`, `.env.example`)
  - [x] 1.1 Create `.gitignore`
  - [x] 1.2 Create `README.md` with celery beat warning
  - [x] 1.3 Create root `.env.example`
- [x] Task 2: Create backend Django project scaffold
  - [x] 2.1 Create backend directory structure and `__init__.py` files
  - [x] 2.2 Create `safenet_backend/settings/base.py`, `development.py`, `production.py`
  - [x] 2.3 Create `safenet_backend/celery.py` and update `__init__.py`
  - [x] 2.4 Create `safenet_backend/urls.py` and `safenet_backend/wsgi.py`
  - [x] 2.5 Create `manage.py`
  - [x] 2.6 Create `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `backend/.env.example`
  - [x] 2.7 Create backend `Dockerfile`
- [x] Task 3: Create health check endpoint and tests (RED → GREEN)
  - [x] 3.1 Write failing test `core/tests/test_health.py`
  - [x] 3.2 Create `core/views/health.py` health endpoint
  - [x] 3.3 Wire `/api/health/` in `urls.py`
  - [x] 3.4 Create `core/tests/conftest.py`
  - [x] 3.5 Create trivial Celery task test
- [x] Task 4: Create frontend Next.js skeleton
  - [x] 4.1 Create `frontend/package.json` with all deps
  - [x] 4.2 Create `frontend/tsconfig.json` (strict mode)
  - [x] 4.3 Create `frontend/next.config.js` and `tailwind.config.ts`
  - [x] 4.4 Create `src/app` structure (layout, globals, auth, dashboard stubs)
  - [x] 4.5 Create `src/middleware.ts` stub
  - [x] 4.6 Create `src/lib/api.ts`, `auth.ts`, `formatters.ts`, `constants.ts` stubs
  - [x] 4.7 Create `src/types/index.ts`
  - [x] 4.8 Create frontend `Dockerfile` and `.env.local.example`
- [x] Task 5: Create Docker Compose configuration
  - [x] 5.1 Create `docker-compose.yml` with all 6 services
  - [x] 5.2 Create `docker-compose.override.yml` for hot-reload
- [x] Task 6: Create GitHub Actions workflows
  - [x] 6.1 Create `.github/workflows/test.yml`
  - [x] 6.2 Create `.github/workflows/deploy.yml`

---

## Dev Agent Record

### Implementation Plan

Story 1.1 is pure infrastructure scaffolding — no business logic. Strategy:
1. Create all directory skeletons and placeholder `__init__.py` files
2. RED phase: write health check test (will fail without the view)
3. GREEN phase: create health view, wire URL
4. Create all config files (Docker Compose, CI/CD, requirements)
5. Create frontend skeleton (package.json, tsconfig, stubs)

### Debug Log

- Used exact package versions from story spec in `requirements.txt` (django==6.0.3, djangorestframework==3.17.1, celery==5.6.3). Verify these resolve on PyPI before running `pip install`.
- `package-lock.json` not generated (requires running `npm install` locally). Run `npm install` in `frontend/` to generate before first Docker build.
- `railway/deploy@v1` GitHub Action used as specified — verify current Railway action version/syntax at railway.app docs before first deploy.
- Celery trivial task test uses `task_always_eager=True` to run synchronously without a broker.

### Completion Notes

All 6 docker-compose services defined (db, redis, web, worker, beat, frontend). Backend Django scaffold created with split settings (base/development/production), Celery configured with hourly beat schedule, health check endpoint at `/api/health/` wired and tested. Frontend Next.js skeleton created with TypeScript strict mode, stub middleware, stub lib files, and component directory structure. GitHub Actions CI/CD created: `test.yml` runs pytest + ESLint on PRs; `deploy.yml` deploys to Railway on main merge. Critical celery beat single-instance constraint documented in README and docker-compose comment.

---

## File List

- `.gitignore`
- `.env.example`
- `README.md`
- `docker-compose.yml`
- `docker-compose.override.yml`
- `.github/workflows/test.yml`
- `.github/workflows/deploy.yml`
- `backend/Dockerfile`
- `backend/manage.py`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/pytest.ini`
- `backend/.env.example`
- `backend/safenet_backend/__init__.py`
- `backend/safenet_backend/celery.py`
- `backend/safenet_backend/wsgi.py`
- `backend/safenet_backend/urls.py`
- `backend/safenet_backend/settings/__init__.py`
- `backend/safenet_backend/settings/base.py`
- `backend/safenet_backend/settings/development.py`
- `backend/safenet_backend/settings/production.py`
- `backend/core/__init__.py`
- `backend/core/apps.py`
- `backend/core/admin/__init__.py`
- `backend/core/engine/__init__.py`
- `backend/core/models/__init__.py`
- `backend/core/tasks/__init__.py`
- `backend/core/views/__init__.py`
- `backend/core/views/health.py`
- `backend/core/tests/__init__.py`
- `backend/core/tests/conftest.py`
- `backend/core/tests/test_health.py`
- `backend/core/tests/test_celery.py`
- `frontend/Dockerfile`
- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/next.config.js`
- `frontend/tailwind.config.ts`
- `frontend/postcss.config.js`
- `frontend/.eslintrc.json`
- `frontend/.env.local.example`
- `frontend/public/.gitkeep`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/globals.css`
- `frontend/src/app/page.tsx`
- `frontend/src/app/(auth)/login/page.tsx`
- `frontend/src/app/(auth)/register/page.tsx`
- `frontend/src/app/(dashboard)/layout.tsx`
- `frontend/src/middleware.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/auth.ts`
- `frontend/src/lib/formatters.ts`
- `frontend/src/lib/constants.ts`
- `frontend/src/types/index.ts`
- `frontend/src/components/ui/.gitkeep`
- `frontend/src/components/common/.gitkeep`
- `frontend/src/components/dashboard/.gitkeep`
- `frontend/src/components/subscriber/.gitkeep`
- `frontend/src/components/settings/.gitkeep`
- `frontend/src/hooks/.gitkeep`
- `frontend/src/stores/.gitkeep`

---

## Change Log

- 2026-04-06: Story 1.1 fully implemented — monorepo initialized, all 6 Docker Compose services configured, Django backend scaffold with health check + tests, Next.js frontend skeleton, GitHub Actions CI/CD pipeline
- 2026-04-06: Code review completed — 8 patch findings, 3 deferred, 13 dismissed

---

## Review Findings

### Patch
- [x] [Review][Patch] SECRET_KEY has insecure default that production silently inherits — added `SECRET_KEY = env("SECRET_KEY")` (no default) in production.py
- [x] [Review][Patch] Sentry SDK init with empty DSN should be guarded — wrapped in `if dsn:` guard
- [x] [Review][Patch] Frontend Dockerfile references `.next/standalone` but next.config.js doesn't enable it — added `output: "standalone"`
- [x] [Review][Patch] No `.dockerignore` files — created for both backend/ and frontend/
- [x] [Review][Patch] CI test.yml references Redis but no Redis service is defined — added redis service to backend-test job
- [x] [Review][Patch] Missing `package-lock.json` breaks `npm ci` in CI and Docker — generated lock file
- [x] [Review][Patch] Deploy workflow has no test gate — added workflow_call trigger + `needs: [test]` in deploy jobs
- [x] [Review][Patch] Health check does not verify DB or Redis connectivity — added DB and Redis checks with degraded status

### Deferred
- [x] [Review][Defer] STRIPE_TOKEN_KEY placeholder is invalid Fernet key — deferred, not used until Story 1.2+
- [x] [Review][Defer] `redis` package unpinned in requirements.txt — deferred, low risk
- [x] [Review][Defer] `production.py` re-creates `environ.Env()` shadowing base — deferred, works in practice
