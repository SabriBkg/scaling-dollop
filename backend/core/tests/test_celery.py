import pytest


def test_celery_app_configured():
    from safenet_backend.celery import app

    assert app.main == "safenet_backend"


def test_celery_beat_schedule_has_hourly_poll():
    from safenet_backend.celery import app

    assert "hourly-retry-poll" in app.conf.beat_schedule
    schedule_entry = app.conf.beat_schedule["hourly-retry-poll"]
    assert schedule_entry["task"] == "core.tasks.poll_failed_payments"
    assert schedule_entry["schedule"] == 3600.0


def test_trivial_task_executes():
    """Verify that a trivial Celery task runs synchronously in ALWAYS_EAGER mode."""
    from safenet_backend.celery import app

    @app.task
    def add(x, y):
        return x + y

    # Run synchronously without a broker (task_always_eager)
    app.conf.task_always_eager = True
    try:
        result = add.delay(2, 3)
        assert result.get() == 5
    finally:
        app.conf.task_always_eager = False
