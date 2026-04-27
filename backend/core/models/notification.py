from django.db import models

from core.models.base import TenantScopedModel

EMAIL_TYPE_CHOICES = [
    ("failure_notice", "Failure Notice"),
    ("final_notice", "Final Notice"),
    ("recovery_confirmation", "Recovery Confirmation"),
]

NOTIFICATION_STATUS_CHOICES = [
    ("sent", "Sent"),
    ("failed", "Failed"),
    ("suppressed", "Suppressed"),
]


class NotificationLog(TenantScopedModel):
    """Records every notification attempt for audit and deduplication."""

    subscriber = models.ForeignKey(
        "core.Subscriber",
        on_delete=models.CASCADE,
        related_name="notification_logs",
    )
    failure = models.ForeignKey(
        "core.SubscriberFailure",
        on_delete=models.CASCADE,
        related_name="notification_logs",
        null=True,
        blank=True,
    )
    email_type = models.CharField(max_length=30, choices=EMAIL_TYPE_CHOICES)
    resend_message_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=NOTIFICATION_STATUS_CHOICES)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "core_notification_log"
        constraints = [
            # Partial unique on status='sent' — multiple suppressed/failed rows
            # for the same (failure, email_type) remain valid (gate-fail rows
            # repeat across polling cycles per Story 4.1 design). Story 4.3
            # Task 6: the source of truth for "sent at most once per
            # (failure, email_type)" — closes the TOCTOU gap left by the
            # gate-check fast path in tasks/notifications.py.
            models.UniqueConstraint(
                fields=["failure", "email_type"],
                condition=models.Q(status="sent"),
                name="unique_sent_notification_per_failure_email_type",
            ),
        ]


class NotificationOptOut(TenantScopedModel):
    """Opt-out record for subscriber email notifications (Story 4.4 stub)."""

    subscriber_email = models.EmailField(max_length=255)

    class Meta:
        db_table = "core_notification_opt_out"
        constraints = [
            models.UniqueConstraint(
                fields=["subscriber_email", "account"],
                name="unique_opt_out_per_account",
            ),
        ]
