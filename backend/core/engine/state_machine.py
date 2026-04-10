"""
State machine constants for the 4-state subscriber status machine.
Full FSM transitions implemented in Story 3.2 (django-fsm).

This stub defines the state constants used across the engine to prevent
magic strings and enable IDE autocomplete from Story 1.3 onwards.
"""

# Subscriber status states (FR16)
STATUS_ACTIVE = "active"
STATUS_RECOVERED = "recovered"
STATUS_PASSIVE_CHURN = "passive_churn"
STATUS_FRAUD_FLAGGED = "fraud_flagged"

ALL_STATUSES = (STATUS_ACTIVE, STATUS_RECOVERED, STATUS_PASSIVE_CHURN, STATUS_FRAUD_FLAGGED)

# Actor identifiers (matches AuditLog.actor choices from Story 1.2)
ACTOR_ENGINE = "engine"
ACTOR_OPERATOR = "operator"
ACTOR_CLIENT = "client"

# Recovery action types (matches DECLINE_RULES action values)
ACTION_RETRY_NOTIFY = "retry_notify"
ACTION_NOTIFY_ONLY = "notify_only"
ACTION_FRAUD_FLAG = "fraud_flag"
ACTION_NO_ACTION = "no_action"

ALL_ACTIONS = (ACTION_RETRY_NOTIFY, ACTION_NOTIFY_ONLY, ACTION_FRAUD_FLAG, ACTION_NO_ACTION)
