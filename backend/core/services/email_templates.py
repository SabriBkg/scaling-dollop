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
