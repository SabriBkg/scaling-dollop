from django.urls import path

from core.views.health import health_check
from core.views.account import account_detail
from core.views.stripe import initiate_stripe_connect, stripe_connect_callback

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("v1/account/me/", account_detail, name="account_detail"),
    path("v1/stripe/connect/", initiate_stripe_connect, name="stripe_connect"),
    path("v1/stripe/callback/", stripe_connect_callback, name="stripe_callback"),
]
