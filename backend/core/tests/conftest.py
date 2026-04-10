import pytest
from django.contrib.auth.models import User
from django.test import Client

from core.models.account import Account


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def user(db):
    """Creates a User — Account is auto-created via signal."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def account(user):
    """Returns the Account auto-created for the test user."""
    return user.account


@pytest.fixture
def auth_client(client, user):
    """Django test client authenticated with JWT — for API tests."""
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    api_client = APIClient()
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client
