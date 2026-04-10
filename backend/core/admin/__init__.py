from django.contrib import admin

from core.models.account import Account, StripeConnection
from core.models.audit import AuditLog

# Operator console customization
admin.site.site_header = "SafeNet Operator Console"
admin.site.site_title = "SafeNet Ops"
admin.site.index_title = "SafeNet Operations Dashboard"


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["id", "owner", "created_at"]
    readonly_fields = ["created_at"]
    search_fields = ["owner__email"]


@admin.register(StripeConnection)
class StripeConnectionAdmin(admin.ModelAdmin):
    list_display = ["account", "stripe_user_id", "created_at"]
    readonly_fields = ["_encrypted_access_token", "created_at", "updated_at"]
    # Never display decrypted token in admin — read-only ciphertext only


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "actor", "action", "outcome", "account", "subscriber_id"]
    readonly_fields = ["timestamp", "actor", "action", "outcome", "account", "subscriber_id", "metadata"]
    list_filter = ["actor", "outcome", "action"]
    search_fields = ["subscriber_id", "action"]

    def has_add_permission(self, request):
        return False  # append-only — no manual creation via admin

    def has_change_permission(self, request, obj=None):
        return False  # immutable

    def has_delete_permission(self, request, obj=None):
        return False  # immutable
