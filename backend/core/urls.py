from django.urls import path

from core.views.health import health_check
from core.views.account import account_detail, complete_profile, accept_dpa, set_engine_mode, set_notification_tone, notification_preview
from core.views.actions import pending_action_list, batch_approve_actions, exclude_subscriber
from core.views.dashboard import dashboard_summary, failed_payments_list
from core.views.stripe import initiate_stripe_connect, stripe_connect_callback
from core.views.subscribers import subscriber_list
from core.views.billing import stripe_billing_webhook, create_checkout_session

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("v1/account/me/", account_detail, name="account_detail"),
    path("v1/account/complete-profile/", complete_profile, name="complete_profile"),
    path("v1/account/dpa/accept/", accept_dpa, name="accept_dpa"),
    path("v1/account/engine/mode/", set_engine_mode, name="set_engine_mode"),
    path("v1/account/notification-tone/", set_notification_tone, name="set_notification_tone"),
    path("v1/account/notification-preview/", notification_preview, name="notification_preview"),
    path("v1/dashboard/summary/", dashboard_summary, name="dashboard_summary"),
    path("v1/dashboard/failed-payments/", failed_payments_list, name="failed_payments_list"),
    path("v1/actions/pending/", pending_action_list, name="pending_action_list"),
    path("v1/actions/batch/", batch_approve_actions, name="batch_approve_actions"),
    path("v1/subscribers/", subscriber_list, name="subscriber_list"),
    path("v1/subscribers/<int:subscriber_id>/exclude/", exclude_subscriber, name="exclude_subscriber"),
    path("v1/stripe/connect/", initiate_stripe_connect, name="stripe_connect"),
    path("v1/stripe/callback/", stripe_connect_callback, name="stripe_callback"),
    path("v1/billing/webhook/", stripe_billing_webhook, name="stripe_billing_webhook"),
    path("v1/billing/checkout/", create_checkout_session, name="create_checkout_session"),
]
