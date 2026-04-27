"""
Tone-aware copy for end-customer notification emails.

GDPR transactional only — zero marketing language permitted in any tone.
This module is the single source of truth for tone copy. The live preview
endpoint and the engine's outbound email both render through it.
"""
from collections.abc import Callable
from dataclasses import dataclass

from core.models.account import (
    DEFAULT_TONE,
    TONE_FRIENDLY,
    TONE_MINIMAL,
    TONE_PROFESSIONAL,
)


@dataclass(frozen=True)
class ToneTemplate:
    subject_default: Callable[[str], str]
    subject_card_expired: Callable[[str], str]
    greeting: str  # may be empty for Minimal
    body_paragraphs: Callable[[str, str, bool], list[str]]
    cta_label: str
    footer: Callable[[str], str]


# Professional — formal, direct, no contractions. Matches the implicit voice
# Story 4.1 shipped with, so this preserves parity for existing accounts.
_PROFESSIONAL = ToneTemplate(
    subject_default=lambda company: f"Action needed: update your payment details — {company}",
    subject_card_expired=lambda company: f"A quick note about your payment — {company}",
    greeting="Hello,",
    body_paragraphs=lambda company, label, is_card_expired: (
        [
            f"We have noticed an issue with your recent payment to {company}: {label}.",
            "Your access continues while you update your details.",
            "You can resolve this by updating your payment details:",
        ]
        if is_card_expired
        else [
            f"We have noticed an issue with your recent payment to {company}: {label}.",
            "You can resolve this by updating your payment details:",
        ]
    ),
    cta_label="Update Payment Details",
    footer=lambda company: f"This email was sent on behalf of {company} by SafeNet.",
)


# Friendly — warm, conversational, contractions allowed.
_FRIENDLY = ToneTemplate(
    subject_default=lambda company: f"Quick heads-up about your {company} payment",
    subject_card_expired=lambda company: f"Hey — your {company} card needs a refresh",
    greeting="Hi there,",
    body_paragraphs=lambda company, label, is_card_expired: (
        [
            f"Just a quick heads-up — we couldn't process your last payment to {company} because of {label}.",
            "Don't worry, you're still all set — your access keeps running while you update your details.",
            "Hit the button below whenever you've got a sec:",
        ]
        if is_card_expired
        else [
            f"Just a quick heads-up — we couldn't process your last payment to {company} because of {label}.",
            "Hit the button below whenever you've got a sec:",
        ]
    ),
    cta_label="Update your details",
    footer=lambda company: f"Sent by {company} via SafeNet.",
)


# Minimal — bare facts, two paragraphs maximum. Cap enforced by construction:
# body_paragraphs always returns a list of length 2.
_MINIMAL = ToneTemplate(
    subject_default=lambda company: f"Payment failed — {company}",
    subject_card_expired=lambda company: f"Card expired — {company}",
    greeting="",
    body_paragraphs=lambda company, label, is_card_expired: [
        f"Payment to {company} failed: {label}.",
        "Update your card to continue — access remains active."
        if is_card_expired
        else "Update your payment method below.",
    ],
    cta_label="Update card",
    footer=lambda company: f"{company} via SafeNet.",
)


TONE_TEMPLATES: dict[str, ToneTemplate] = {
    TONE_PROFESSIONAL: _PROFESSIONAL,
    TONE_FRIENDLY: _FRIENDLY,
    TONE_MINIMAL: _MINIMAL,
}


def get_template(tone: str | None) -> ToneTemplate:
    """Return the template for the given tone, falling back to the default."""
    return TONE_TEMPLATES.get(tone or DEFAULT_TONE, TONE_TEMPLATES[DEFAULT_TONE])


# ---------------------------------------------------------------------------
# Final notice (Story 4.3)
# ---------------------------------------------------------------------------
# A separate dataclass — the field shapes diverge from ToneTemplate (no card-
# expired branch, decline-code-agnostic copy), so widening ToneTemplate would
# leave dead optional fields on every existing template. See Story 4.3 Task 1.


@dataclass(frozen=True)
class FinalNoticeTemplate:
    subject: Callable[[str], str]            # company → subject
    greeting: str                            # may be empty
    body_paragraphs: Callable[[str], list[str]]   # company → paragraphs (raw)
    cta_label: str
    footer: Callable[[str], str]


_FINAL_NOTICE_PROFESSIONAL = FinalNoticeTemplate(
    subject=lambda company: f"Final attempt to process your payment — {company}",
    greeting="Hello,",
    body_paragraphs=lambda company: [
        f"This is our final attempt to process your payment to {company}.",
        "If it does not succeed, your subscription will be paused. You can avoid this by updating your payment details now:",
    ],
    cta_label="Update Payment Details",
    footer=lambda company: f"This email was sent on behalf of {company} by SafeNet.",
)


_FINAL_NOTICE_FRIENDLY = FinalNoticeTemplate(
    subject=lambda company: f"Heads up — last try on your {company} payment",
    greeting="Hi there,",
    body_paragraphs=lambda company: [
        f"Just a heads-up — this is our last try at processing your payment to {company}.",
        "If it doesn't go through, your subscription will be paused. You can sort this out right now by updating your details:",
    ],
    cta_label="Update your details",
    footer=lambda company: f"Sent by {company} via SafeNet.",
)


_FINAL_NOTICE_MINIMAL = FinalNoticeTemplate(
    subject=lambda company: f"Final attempt — {company}",
    greeting="",
    body_paragraphs=lambda company: [
        f"Final attempt to process your payment to {company}.",
        "If unsuccessful, your subscription will be paused. Update your card to keep it active:",
    ],
    cta_label="Update card",
    footer=lambda company: f"{company} via SafeNet.",
)


FINAL_NOTICE_TEMPLATES: dict[str, FinalNoticeTemplate] = {
    TONE_PROFESSIONAL: _FINAL_NOTICE_PROFESSIONAL,
    TONE_FRIENDLY: _FINAL_NOTICE_FRIENDLY,
    TONE_MINIMAL: _FINAL_NOTICE_MINIMAL,
}


def get_final_notice_template(tone: str | None) -> FinalNoticeTemplate:
    """Return the final-notice template for the given tone, falling back to default."""
    return FINAL_NOTICE_TEMPLATES.get(
        tone or DEFAULT_TONE, FINAL_NOTICE_TEMPLATES[DEFAULT_TONE]
    )


# ---------------------------------------------------------------------------
# Recovery confirmation (Story 4.3)
# ---------------------------------------------------------------------------
# No CTA — recovery has already happened, no action is required from the
# subscriber. body_paragraphs cap is enforced by construction (≤2 strings).


@dataclass(frozen=True)
class RecoveryConfirmationTemplate:
    subject: Callable[[str], str]
    greeting: str
    body_paragraphs: Callable[[str], list[str]]   # ≤ 2 strings — cap by construction
    footer: Callable[[str], str]
    # NO cta_label field — confirmation has no button


_RECOVERY_CONFIRMATION_PROFESSIONAL = RecoveryConfirmationTemplate(
    subject=lambda company: f"Payment confirmed — {company}",
    greeting="Hello,",
    body_paragraphs=lambda company: [
        f"Your payment to {company} has been confirmed.",
        "Thank you for updating your details.",
    ],
    footer=lambda company: f"This email was sent on behalf of {company} by SafeNet.",
)


_RECOVERY_CONFIRMATION_FRIENDLY = RecoveryConfirmationTemplate(
    subject=lambda company: f"All sorted — payment confirmed for {company}",
    greeting="Hi there,",
    body_paragraphs=lambda company: [
        f"All sorted — your payment to {company} has been confirmed.",
        "Thanks for updating your details!",
    ],
    footer=lambda company: f"Sent by {company} via SafeNet.",
)


_RECOVERY_CONFIRMATION_MINIMAL = RecoveryConfirmationTemplate(
    subject=lambda company: f"Payment confirmed — {company}",
    greeting="",
    body_paragraphs=lambda company: [
        f"Payment to {company} confirmed.",
    ],
    footer=lambda company: f"{company} via SafeNet.",
)


RECOVERY_CONFIRMATION_TEMPLATES: dict[str, RecoveryConfirmationTemplate] = {
    TONE_PROFESSIONAL: _RECOVERY_CONFIRMATION_PROFESSIONAL,
    TONE_FRIENDLY: _RECOVERY_CONFIRMATION_FRIENDLY,
    TONE_MINIMAL: _RECOVERY_CONFIRMATION_MINIMAL,
}


def get_recovery_confirmation_template(tone: str | None) -> RecoveryConfirmationTemplate:
    """Return the recovery-confirmation template for the given tone, falling back to default."""
    return RECOVERY_CONFIRMATION_TEMPLATES.get(
        tone or DEFAULT_TONE, RECOVERY_CONFIRMATION_TEMPLATES[DEFAULT_TONE]
    )
