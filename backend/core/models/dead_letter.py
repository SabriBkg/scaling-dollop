from django.db import models

from core.models.base import TenantScopedModel


class DeadLetterLog(TenantScopedModel):
    """
    Records unhandled Celery task exceptions for operator review.
    NFR-R5: Dead letter logging on task failure.
    """
    task_name = models.CharField(max_length=255)
    error = models.TextField()

    class Meta:
        db_table = "core_dead_letter_log"

    def __str__(self):
        return f"DeadLetterLog({self.task_name}, {self.created_at})"
