"""
Audit log write helper.

RULE: All audit events must be written via write_audit_event() — never inline.
This enforces the append-only constraint and provides a single, auditable write path.
"""

from core.models.audit import AuditLog


def write_audit_event(
    subscriber: str | None,
    actor: str,
    action: str,
    outcome: str,
    metadata: dict | None = None,
    account=None,
) -> AuditLog:
    """
    Create an immutable audit log entry.

    Args:
        subscriber: Subscriber identifier string (None for account-level events)
        actor: One of "engine", "operator", "client"
        action: snake_case verb describing what happened, e.g. "retry_scheduled"
        outcome: "success" | "failed" | "skipped"
        metadata: Additional context dict (optional)
        account: Account instance (optional for account-level events)

    Returns:
        The created AuditLog instance.

    Example:
        write_audit_event(
            subscriber=str(subscriber.id),
            actor="engine",
            action="retry_scheduled",
            outcome="success",
            metadata={"decline_code": "insufficient_funds", "retry_number": 1},
            account=subscriber.account,
        )
    """
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        outcome=outcome,
        account=account,
        subscriber_id=subscriber,
        metadata=metadata or {},
    )
