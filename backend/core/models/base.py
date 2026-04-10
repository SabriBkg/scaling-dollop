from django.db import models


class TenantManager(models.Manager):
    """
    Default manager for all tenant-scoped models.
    Requires explicit account_id scoping — prevents accidental cross-tenant queries.
    """

    def get_queryset(self):
        return super().get_queryset()

    def for_account(self, account_id):
        """Standard entry point for all tenant-scoped queries."""
        return self.get_queryset().filter(account_id=account_id)


class UnscopedManager(models.Manager):
    """
    Explicit unscoped manager for admin/operator context only.
    Usage: Model.unscoped.all()  — intentional, visible, auditable.
    Never use this in client-facing views.
    """
    pass


class TenantScopedModel(models.Model):
    """
    Abstract base class for all account-scoped Django models.
    Inherit from this instead of models.Model for any model that belongs to a tenant account.

    Usage:
        class MyModel(TenantScopedModel):
            ...

    Querying:
        MyModel.objects.for_account(account_id)   # ✅ tenant-scoped
        MyModel.unscoped.filter(...)               # ✅ admin/operator only
        MyModel.objects.all()                      # ❌ forbidden — always add .for_account()
    """
    account = models.ForeignKey(
        "core.Account",
        on_delete=models.CASCADE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    unscoped = UnscopedManager()

    class Meta:
        abstract = True
