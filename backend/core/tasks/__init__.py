from safenet_backend.celery import app


@app.task
def poll_failed_payments():
    """Stub — Story 3.2 implements the full retry engine."""
    pass
