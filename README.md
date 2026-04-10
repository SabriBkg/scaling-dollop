# SafeNet

Automated payment failure recovery platform for SaaS businesses.

## Quick Start

```bash
cp .env.example .env
docker compose up
```

Services available:
- **Backend (Django):** http://localhost:8000
- **Frontend (Next.js):** http://localhost:3000
- **API Health:** http://localhost:8000/api/health/

## Architecture

| Service | Technology | Port |
|---------|------------|------|
| `db` | PostgreSQL 16 | 5432 |
| `redis` | Redis 7 | 6379 |
| `web` | Django 6 (dev server) | 8000 |
| `worker` | Celery worker | — |
| `beat` | Celery beat scheduler | — |
| `frontend` | Next.js 14 | 3000 |

## Development

### Backend

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

### Frontend

```bash
cd frontend
npm ci
npm run lint
npm run dev
```

## Deployment

Deployed to [Railway](https://railway.app) via GitHub Actions on merge to `main`.

Required GitHub Secrets:
- `RAILWAY_TOKEN` — Railway API token

### Railway Services

| Railway Service | Source |
|----------------|--------|
| `safenet-backend` | `backend/` |
| `safenet-frontend` | `frontend/` |

> ⚠️ **celery beat must run as exactly one Railway instance.** Multiple instances cause double-firing of scheduled retries, which would trigger duplicate payment retries against Stripe — a serious financial bug. Set `replicas: 1` in the Railway `beat` service configuration.

## Environment Variables

Copy `.env.example` to `.env` and fill in the values before running locally.

See `backend/.env.example` for backend-specific variables and `frontend/.env.local.example` for frontend-specific variables.
