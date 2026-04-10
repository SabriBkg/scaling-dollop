import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    """Unauthenticated DRF APIClient for public endpoint tests."""
    return APIClient()
