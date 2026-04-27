from django.contrib.auth.models import User
from django.db import models

from core.models.base import TenantManager


ACTOR_ENGINE = "engine"
ACTOR_OPERATOR = "operator"
ACTOR_CLIENT = "client"
ACTOR_SUBSCRIBER = "subscriber"  # Story 4.4 — end-customer-side opt-out actor

ACTOR_CHOICES = [
    (ACTOR_ENGINE, "Engine"),
    (ACTOR_OPERATOR, "Operator"),
    (ACTOR_CLIENT, "Client"),
    (ACTOR_SUBSCRIBER, "Subscriber"),
]


class AuditLogManager(TenantManager):
    """AuditLog-specific manager that inherits for_account() from TenantManager."""
    pass


class AuditLog(models.Model):
    """
    Append-only audit trail for all engine actions, status changes, and operator interventions.

    CRITICAL: No update or delete paths exist in the application layer.
    Never call AuditLog.objects.filter(...).update(...)  — write-only via write_audit_event().
    Retention: 36 months (NFR-D2).
    """
    # subscriber may be null for account-level events
    subscriber_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    account = models.ForeignKey(
        "core.Account",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
    )
    actor = models.CharField(max_length=20, choices=ACTOR_CHOICES)
    action = models.CharField(max_length=100)  # snake_case verb, e.g. "retry_scheduled"
    outcome = models.CharField(max_length=50)  # "success" | "failed" | "skipped"
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = AuditLogManager()

    class Meta:
        db_table = "core_audit_log"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("AuditLog records are immutable — append-only.")
        super().save(*args, **kwargs)
