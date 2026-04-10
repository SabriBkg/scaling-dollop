from django.db import models

from core.engine.state_machine import ALL_STATUSES, STATUS_ACTIVE
from core.models.base import TenantScopedModel


class Subscriber(TenantScopedModel):
    """
    A payment customer belonging to a tenant account.
    Keyed on stripe_customer_id + account for uniqueness.
    """
    stripe_customer_id = models.CharField(max_length=255, db_index=True)
    email = models.EmailField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=30,
        choices=[(s, s) for s in ALL_STATUSES],
        default=STATUS_ACTIVE,
    )

    class Meta:
        db_table = "core_subscriber"
        constraints = [
            models.UniqueConstraint(
                fields=["stripe_customer_id", "account"],
                name="unique_subscriber_per_account",
            ),
        ]

    def __str__(self):
        return f"Subscriber({self.stripe_customer_id}, {self.email})"


class SubscriberFailure(TenantScopedModel):
    """
    A single failed payment event for a subscriber.
    Keyed on payment_intent_id for idempotency.
    """
    subscriber = models.ForeignKey(
        Subscriber,
        on_delete=models.CASCADE,
        related_name="failures",
    )
    payment_intent_id = models.CharField(max_length=255, unique=True)
    decline_code = models.CharField(max_length=100)
    amount_cents = models.IntegerField()
    payment_method_country = models.CharField(max_length=10, null=True, blank=True)
    failure_created_at = models.DateTimeField()
    classified_action = models.CharField(max_length=50)

    class Meta:
        db_table = "core_subscriber_failure"

    def __str__(self):
        return f"SubscriberFailure({self.payment_intent_id}, {self.decline_code})"
