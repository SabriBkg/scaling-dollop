from django.urls import path

from core.views.health import health_check
from core.views.account import account_detail, complete_profile
from core.views.dashboard import dashboard_summary
from core.views.stripe import initiate_stripe_connect, stripe_connect_callback

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("v1/account/me/", account_detail, name="account_detail"),
    path("v1/account/complete-profile/", complete_profile, name="complete_profile"),
    path("v1/dashboard/summary/", dashboard_summary, name="dashboard_summary"),
    path("v1/stripe/connect/", initiate_stripe_connect, name="stripe_connect"),
    path("v1/stripe/callback/", stripe_connect_callback, name="stripe_callback"),
]
