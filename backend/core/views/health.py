from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    checks = {"status": "ok", "database": "ok", "redis": "ok"}
    status_code = 200

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        checks["database"] = "unavailable"
        checks["status"] = "degraded"
        status_code = 503

    # Check Redis
    try:
        from django.conf import settings
        from redis import Redis

        redis_url = getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0")
        r = Redis.from_url(redis_url, socket_connect_timeout=2)
        try:
            r.ping()
        finally:
            r.close()
    except Exception:
        checks["redis"] = "unavailable"
        checks["status"] = "degraded"
        status_code = 503

    return Response(checks, status=status_code)
