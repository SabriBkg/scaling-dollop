import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "safenet_backend.settings.production")

app = Celery("safenet_backend")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(["core"])

app.conf.beat_schedule = {
    "hourly-retry-poll": {
        "task": "core.tasks.polling.poll_new_failures",
        "schedule": 3600.0,
    },
}
