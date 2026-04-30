# Story 3.3 (v1): Per-Row Send & Manual Resolve

Status: draft

> **v1 scope (post-2026-04-29 simplification).** Replaces the quarantined `3-3-card-update-detection-immediate-retry.md` (v0). v1 has no automated retries — clients trigger every email by hand from the failed-payments dashboard. See `_bmad-output/sprint-change-proposal-2026-04-29.md`.

## Story

As a Mid-tier founder,
I want to trigger a recommended (or chosen) dunning email per failed-payment row, and to manually mark failures as resolved,
So that I act on each case without leaving the dashboard.

## Acceptance Criteria

1. **Given** a row with status `Active` and a non-null recommended email type **When** the client clicks "Send recommended" **Then** `POST /api/v1/subscribers/{id}/send-email/` is called with `{email_type: <recommended>}` **And** the dispatch service runs the opt-out check, then queues the Resend send **And** the audit log records `{action: "email_sent", email_type, trigger: "client_manual"}` (FR53)

2. **Given** a row with status `Active` **When** the client opens the per-row dropdown "Send specific email" **Then** options shown are: Update payment / Retry reminder / Final notice **And** selecting any option sends that email type via the same endpoint (FR53)

3. **Given** a row with any status **When** the client clicks "Mark resolved" **Then** the subscriber transitions to `Recovered` status with a manual-resolution audit note **And** the row's badge updates to Recovered (FR55)

4. **Given** a row **When** the client clicks "Exclude from future recommendations" **Then** future recommendations for this subscriber are suppressed (recommended_email returns null) **And** the exclusion is recorded in the audit log

5. **Given** an opted-out subscriber **When** the client triggers any send for that subscriber's row **Then** the dispatch service rejects the send with a clear error **And** no Resend call is made (FR26, FR27)

6. **Given** an account hitting the rate limit (10 sends/min) **When** the client triggers an 11th send within the window **Then** the API responds 429 with retry-after seconds **And** the frontend surfaces a non-blocking toast

## Tasks / Subtasks

> TBD — expand via SM (story management) workflow per-story. Source-of-truth ACs above.

## Dev Notes

- FRs covered: FR53, FR55, FR17 (manual-resolve transition), FR26, FR27 (opt-out enforcement)
- Endpoint: `POST /api/v1/subscribers/{id}/send-email/` body `{email_type}`; rate-limit DRF throttle 10/min/account.
- DPA gate (Story 3.1 v1) must be satisfied before any send — endpoint returns 403 DPA_REQUIRED otherwise.
- Opt-out check uses Story 4.4's `NotificationOptOut` model.
