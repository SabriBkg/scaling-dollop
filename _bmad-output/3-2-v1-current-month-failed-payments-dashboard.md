# Story 3.2 (v1): Current-Month Failed-Payments Dashboard

Status: draft

> **v1 scope (post-2026-04-29 simplification).** Replaces the quarantined `3-2-autopilot-recovery-engine-rule-execution-4-state-status-machine.md` (v0). The current-month failed-payments list is now the dashboard's primary working surface — no separate review queue, no autopilot vs supervised mode. See `_bmad-output/sprint-change-proposal-2026-04-29.md`.

## Story

As a Mid-tier founder,
I want a dashboard view of all failed payments from the current month with recommended emails per row,
So that I can review and act on each at my own pace.

## Acceptance Criteria

1. **Given** the dashboard loads **When** the failed-payments list renders **Then** rows are filtered to `failure_created_at` within the current calendar month (account timezone) **And** each row displays: subscriber name + email, amount in cents formatted to €, plain-language decline reason via `DeclineCodeExplainer`, recommended email type chip, status badge (Active / Recovered / Passive Churn / Fraud Flagged), and last-email-sent timestamp if any

2. **Given** the failed-payments list **When** the client clicks the column headers **Then** the list sorts by amount (desc/asc) or date (desc/asc) — selection persists in URL query params

3. **Given** a Free-tier client **When** they view the failed-payments list **Then** action buttons (Send, Mark resolved, Exclude) are disabled with an upgrade CTA tooltip

4. **Given** zero failed payments for the current month **When** the list renders **Then** the empty state shows: "No failed payments this month."

5. **Given** a `fraud_flagged` row **When** rendered **Then** the recommended email chip displays "—" (no recommendation) **And** the row has an amber border to distinguish it from regular Active rows

## Tasks / Subtasks

> TBD — expand via SM (story management) workflow per-story. Source-of-truth ACs above.

## Dev Notes

- FRs covered: FR52, FR16 (status display), FR19 (fraud flag visual)
- UX-DRs covered: UX-DR9 (`SubscriberCard` row), UX-DR10 (`Badge` variants), UX-DR16 (current-month list as primary surface)
- Recommended email chip is derived per Story 3.5 (v1) rule engine logic.
