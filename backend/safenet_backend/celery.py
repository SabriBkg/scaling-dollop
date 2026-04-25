import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "safenet_backend.settings.production")

app = Celery("safenet_backend")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(["core"])

app.conf.beat_schedule = {
    "daily-failure-poll": {
        "task": "core.tasks.polling.poll_new_failures",
        "schedule": 86400.0,
    },
    "daily-trial-expiration": {
        "task": "core.tasks.trial_expiration.expire_trials",
        "schedule": 86400.0,
    },
    "retry-dispatcher-15min": {
        "task": "core.tasks.retry.execute_pending_retries",
        "schedule": 900.0,
    },
}
