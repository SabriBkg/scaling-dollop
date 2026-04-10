import pytest


@pytest.mark.django_db
def test_health_check(client):
    response = client.get("/api/health/")
    # Status is 200 (all healthy) or 503 (degraded, e.g. Redis unavailable in test)
    assert response.status_code in (200, 503)
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert "database" in data
    assert "redis" in data


@pytest.mark.django_db
def test_health_check_database_field(client):
    response = client.get("/api/health/")
    data = response.json()
    # Database should always be reachable in django_db tests
    assert data["database"] == "ok"


@pytest.mark.django_db
def test_health_check_method_not_allowed(client):
    response = client.post("/api/health/")
    assert response.status_code == 405
