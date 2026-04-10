from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models.account import Account


@receiver(post_save, sender=User)
def create_account_for_new_user(sender, instance, created, **kwargs):
    """
    Auto-creates an Account when a new User is created.
    Enforces the one-user-per-account MVP constraint (FR48).
    Staff/operator users do not receive client Accounts (NFR-S4).
    """
    if created and not instance.is_staff:
        Account.objects.create(owner=instance)
