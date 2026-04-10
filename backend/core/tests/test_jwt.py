import pytest


@pytest.mark.django_db
class TestJWTAuth:
    def test_obtain_token_with_valid_credentials(self, client, user):
        response = client.post(
            "/api/v1/auth/token/",
            {"username": "testuser", "password": "testpass123"},
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert "access" in data
        assert "refresh" in data

    def test_obtain_token_with_invalid_credentials(self, client):
        response = client.post(
            "/api/v1/auth/token/",
            {"username": "nobody", "password": "wrong"},
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_token_contains_account_id(self, client, user, account):
        import base64
        import json

        response = client.post(
            "/api/v1/auth/token/",
            {"username": "testuser", "password": "testpass123"},
            content_type="application/json",
        )
        access_token = response.json()["access"]
        # Decode JWT payload (middle segment, base64-encoded)
        payload_b64 = access_token.split(".")[1]
        # Add padding if needed
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        assert payload["account_id"] == account.id

    def test_health_endpoint_is_public(self, client):
        """Health check must remain accessible without authentication."""
        response = client.get("/api/health/")
        assert response.status_code in (200, 503)

    def test_refresh_token_returns_new_access_token(self, client, user):
        # Obtain initial tokens
        tokens = client.post(
            "/api/v1/auth/token/",
            {"username": "testuser", "password": "testpass123"},
            content_type="application/json",
        ).json()

        # Refresh
        response = client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": tokens["refresh"]},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert "access" in response.json()

    def test_protected_endpoint_rejects_unauthenticated(self, client):
        response = client.get("/api/v1/account/me/")
        assert response.status_code == 401

    def test_protected_endpoint_accessible_with_jwt(self, auth_client, account):
        response = auth_client.get("/api/v1/account/me/")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == account.id

    def test_admin_path_is_disabled(self, client):
        """The /admin/ path must return 404 — not redirected, disabled."""
        response = client.get("/admin/")
        assert response.status_code == 404

    def test_ops_console_is_accessible(self, client):
        """The /ops-console/ path must exist (returns 302 redirect to login for unauthenticated)."""
        response = client.get("/ops-console/")
        assert response.status_code in (200, 302)
