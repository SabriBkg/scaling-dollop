from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Use DATABASE_URL from env (set to postgres via docker-compose, or sqlite for quick runs)
# base.py already reads DATABASE_URL; no override needed here.

# Allow all CORS in development
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
