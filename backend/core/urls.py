from django.urls import path

from core.views.health import health_check
from core.views.account import account_detail

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("v1/account/me/", account_detail, name="account_detail"),
]
