"""
Human-readable labels for Stripe decline codes.

Used by the dashboard API to translate raw decline codes into
user-friendly descriptions. No raw Stripe codes should ever be
shown in the UI.
"""

DECLINE_CODE_LABELS: dict[str, str] = {
    "card_expired": "Card expired",
    "expired_card": "Card expired",
    "insufficient_funds": "Insufficient funds",
    "do_not_honor": "Payment declined by bank",
    "generic_decline": "Payment declined",
    "fraudulent": "Fraud flagged",
    "lost_card": "Card reported lost or stolen",
    "stolen_card": "Card reported lost or stolen",
    "card_lost_or_stolen": "Card reported lost or stolen",
    "pickup_card": "Card reported lost or stolen",
    "card_velocity_exceeded": "Too many payment attempts",
    "authentication_required": "Authentication required",
    "authentication_failure": "Authentication failed",
    "processing_error": "Processing error",
    "issuer_temporarily_unavailable": "Bank temporarily unavailable",
    "expired_token": "Payment method expired",
    "no_account": "Account closed",
    "card_not_supported": "Card not supported",
    "currency_not_supported": "Currency not supported",
    "service_not_allowed": "Service not allowed",
    "transaction_not_allowed": "Transaction not allowed",
    "not_permitted": "Transaction not permitted",
    "restricted_card": "Restricted card",
    "security_violation": "Security violation",
    "stop_payment_order": "Stop payment order",
    "revocation_of_authorization": "Authorization revoked",
    "revocation_of_all_authorizations": "Authorization revoked",
    "invalid_account": "Invalid account",
    "new_account_information_available": "Card update required",
    "try_again_later": "Temporary issue",
    "reenter_transaction": "Processing error",
    "no_action_taken": "Processing error",
    "duplicate_transaction": "Duplicate transaction",
    "invalid_amount": "Invalid amount",
    "incorrect_pin": "Incorrect PIN",
    "incorrect_cvc": "Incorrect CVC",
    "pin_try_exceeded": "PIN attempts exceeded",
    "offline_pin_required": "PIN required",
    "online_or_offline_pin_required": "PIN required",
    "_default": "Payment declined",
}
