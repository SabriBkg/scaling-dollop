# Story 3.4 (v1): Bulk Send & Status Polling

Status: draft

> **v1 scope (post-2026-04-29 simplification).** Replaces the quarantined `3-4-supervised-mode-pending-action-queue-batch-approval.md` (v0). v1 has no Supervised mode review queue — bulk action runs over selected rows in the failed-payments dashboard. Polling is daily (NFR-R1) and is the source of truth for Active → Recovered / Passive Churn transitions. See `_bmad-output/sprint-change-proposal-2026-04-29.md`.

## Story

As a Mid-tier founder,
I want to bulk-send dunning emails for multiple selected rows, and trust SafeNet to detect when subscribers pay or cancel through daily polling,
So that I cover the high-leverage moves quickly without micromanaging each subscriber.

## Acceptance Criteria

1. **Given** the failed-payments list **When** the client selects rows via the checkbox column **Then** the bulk action toolbar slides up showing the selected count **And** primary action: "Send recommended (N)" **And** secondary action: "Send specific (chosen type)" **And** tertiary actions: "Mark resolved (N)", "Exclude (N)" (FR54)

2. **Given** the client clicks "Send recommended (N)" **When** the confirmation dialog opens **Then** it shows the N rows with each row's recommended email type pre-listed **And** a "Send all" button confirms the bulk dispatch

3. **Given** the bulk send confirms **When** `POST /api/v1/subscribers/batch-send-email/` is called **Then** each row dispatches with its own email type **And** partial failures surface per-row in a result toast (UX-DR8 reframed) **And** the audit log records one entry per send

4. **Given** the daily polling Celery task runs **When** it detects a subscription state of `cancelled`, `unpaid`, `paused`, or `cancel_at_period_end` **Then** the subscriber transitions Active → Passive Churn with the specific reason recorded (FR18)

5. **Given** the daily polling Celery task runs **When** it detects a previously-failed PaymentIntent now succeeded **Then** the subscriber transitions Active → Recovered (FR17) **And** the recovery confirmation email is dispatched per FR25 (Story 4.3)

6. **Given** Free-tier client **When** they attempt to multi-select **Then** the bulk toolbar surfaces an upgrade CTA; bulk send is paid-only

## Tasks / Subtasks

> TBD — expand via SM (story management) workflow per-story. Source-of-truth ACs above.

## Dev Notes

- FRs covered: FR54, FR17, FR18, FR46
- UX-DRs covered: UX-DR8 (reframed for v1)
- Bulk endpoint: `POST /api/v1/subscribers/batch-send-email/` body `{ids: [...], mode: "recommended"|"specific", email_type?: ...}`
- Daily polling task: `poll_new_failures` (also covers Story 2.2 polling cadence). Status transitions are FSM-protected.
