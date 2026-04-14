from django.db import models

from core.models.base import TenantScopedModel


STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_EXCLUDED = "excluded"

PENDING_ACTION_STATUSES = [
    (STATUS_PENDING, "Pending"),
    (STATUS_APPROVED, "Approved"),
    (STATUS_EXCLUDED, "Excluded"),
]


class PendingAction(TenantScopedModel):
    """
    A queued recovery action awaiting client approval in Supervised mode.
    Created when engine detects a failure but account is in supervised mode.
    """
    subscriber = models.ForeignKey(
        "core.Subscriber",
        on_delete=models.CASCADE,
        related_name="pending_actions",
    )
    failure = models.ForeignKey(
        "core.SubscriberFailure",
        on_delete=models.CASCADE,
        related_name="pending_actions",
    )
    recommended_action = models.CharField(max_length=50)
    recommended_retry_cap = models.IntegerField()
    recommended_payday_aware = models.BooleanField()
    status = models.CharField(
        max_length=20,
        choices=PENDING_ACTION_STATUSES,
        default=STATUS_PENDING,
    )

    class Meta:
        db_table = "core_pending_action"

    def __str__(self):
        return f"PendingAction({self.id}, {self.recommended_action}, {self.status})"
