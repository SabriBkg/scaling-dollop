# Story 3.5 (v1): Recommended-Email Mapping (Decline Code → Email Type)

Status: draft

> **v1 scope (post-2026-04-29 simplification).** Replaces the quarantined `3-5-subscriber-status-cards-attention-bar.md` (v0). v1 reuses the v0 `DECLINE_RULES` config but consults only the `action` field — `retry_cap`, `payday_aware`, `geo_block` remain in the config (v2 reactivation-ready) and are intentionally not consulted. See `_bmad-output/sprint-change-proposal-2026-04-29.md`.

## Story

As a developer,
I want the rule engine to map each decline code to a recommended email type and time-since-failure escalation,
So that the dashboard's per-row recommendation is data-driven and testable.

## Acceptance Criteria

1. **Given** the `DECLINE_RULES` config **When** loaded **Then** the action vocabulary is `{update_payment, retry_reminder, final_notice, fraud_flag, no_recommendation}` (FR10) **And** retry_cap, payday_aware, geo_block fields remain in the config but are not consulted in v1 (v2 reactivation-ready)

2. **Given** a failure **When** `get_recommended_email(decline_code, days_since_failure)` is called **Then** day 0–6 returns `update_payment` **And** day 7–13 returns `retry_reminder` **And** day 14+ returns `final_notice` **And** `fraudulent` decline code returns `fraud_flag` (no recommendation) **And** unknown decline codes via `_default` return `update_payment`

3. **Given** the recommended email logic **When** unit tests run via pytest **Then** the module is pure-Python, zero DB dependency, fully exercisable without fixtures **And** branch coverage ≥95% for the recommendation function

4. **Given** a `SubscriberFailure` row serialized for the frontend **When** the response is built **Then** the response includes `recommended_email_type` derived from the rule engine + time-since-failure **And** `geo_warning: true` is included for SEPA/UK payment-method countries (informational only)

## Tasks / Subtasks

> TBD — expand via SM (story management) workflow per-story. Source-of-truth ACs above.

## Dev Notes

- FRs covered: FR10
- Rule engine module: `core/engine/rules.py` (already established in Story 1.3 — extend, don't rebuild).
- v2 fields preserved unchanged in config: `retry_cap`, `payday_aware`, `geo_block` — for the v2 retry-engine reactivation off `archive/v0-recovery-engine`.
