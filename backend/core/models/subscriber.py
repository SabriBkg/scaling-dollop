from django.db import models
from django.dispatch import receiver
from django_fsm import FSMField, transition, TransitionNotAllowed  # noqa: F401
from django_fsm.signals import post_transition

from core.engine.state_machine import (
    ALL_STATUSES,
    STATUS_ACTIVE,
    STATUS_RECOVERED,
    STATUS_PASSIVE_CHURN,
    STATUS_FRAUD_FLAGGED,
)
from core.models.base import TenantScopedModel


class Subscriber(TenantScopedModel):
    """
    A payment customer belonging to a tenant account.
    Keyed on stripe_customer_id + account for uniqueness.
    Status managed by django-fsm — transitions enforced via decorated methods.
    """
    stripe_customer_id = models.CharField(max_length=255, db_index=True)
    email = models.EmailField(max_length=255, blank=True, default="")
    excluded_from_automation = models.BooleanField(default=False)
    last_payment_method_fingerprint = models.CharField(max_length=255, null=True, blank=True)
    status = FSMField(
        max_length=30,
        choices=[(s, s) for s in ALL_STATUSES],
        default=STATUS_ACTIVE,
    )

    @transition(field=status, source=STATUS_ACTIVE, target=STATUS_RECOVERED)
    def recover(self):
        """Transition active → recovered when retry succeeds."""
        pass

    @transition(field=status, source=STATUS_ACTIVE, target=STATUS_PASSIVE_CHURN)
    def mark_passive_churn(self):
        """Transition active → passive_churn when retries exhausted or subscription cancelled."""
        pass

    @transition(field=status, source=STATUS_ACTIVE, target=STATUS_FRAUD_FLAGGED)
    def mark_fraud_flagged(self):
        """Transition active → fraud_flagged on fraudulent decline code."""
        pass

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
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "core_subscriber_failure"

    def __str__(self):
        return f"SubscriberFailure({self.payment_intent_id}, {self.decline_code})"


@receiver(post_transition, sender=Subscriber)
def on_subscriber_status_transition(sender, instance, name, source, target, **kwargs):
    """Write audit event on every FSM status transition."""
    from core.services.audit import write_audit_event

    write_audit_event(
        subscriber=str(instance.id),
        actor="engine",
        action=f"status_{target}",
        outcome="success",
        metadata={"from": source, "to": target},
        account=instance.account,
    )
