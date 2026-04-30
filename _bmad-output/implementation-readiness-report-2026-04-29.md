---
stepsCompleted: [1, 2, 3, 4, 5, 6]
remediationPass: 2026-04-29
project_name: SafeNet
date: 2026-04-29
status: ready-with-caveats
inputDocuments:
  - _bmad-output/prd.md
  - _bmad-output/architecture.md
  - _bmad-output/epics.md
  - _bmad-output/ux-design-specification.md
  - _bmad-output/sprint-change-proposal-2026-04-29.md
storyFiles:
  - 1-1-monorepo-initialization-docker-compose-ci-cd-pipeline.md
  - 1-2-django-core-tenant-isolation-jwt-auth-stripe-token-encryption.md
  - 1-3-decline-code-rule-engine-config-compliance-module.md
  - 1-4-next-js-frontend-skeleton-design-token-system-state-management.md
  - 2-1-user-registration-stripe-connect-oauth.md
  - 2-1b-post-oauth-profile-completion-login-fix.md
  - 2-2-90-day-retroactive-scan-background-job.md
  - 2-3-authenticated-dashboard-shell-navigation.md
  - 2-4-failure-landscape-dashboard-kpi-cards.md
  - 2-5-subscription-tiers-trial-mechanics-free-tier-degradation.md
  - 3-1-dpa-acceptance-engine-mode-selection-flow.md  # QUARANTINED v0
  - 3-2-autopilot-recovery-engine-rule-execution-4-state-status-machine.md  # QUARANTINED v0
  - 3-3-card-update-detection-immediate-retry.md  # QUARANTINED v0
  - 3-4-supervised-mode-pending-action-queue-batch-approval.md  # QUARANTINED v0
  - 3-5-subscriber-status-cards-attention-bar.md  # QUARANTINED v0
  - 4-1-resend-integration-branded-failure-notification-email.md  # REVISE REQUIRED
  - 4-2-tone-selector-settings-live-notification-preview.md  # REVISE REQUIRED
  - 4-3-final-notice-recovery-confirmation-emails.md  # REVISE REQUIRED
  - 4-4-opt-out-mechanism-notification-suppression.md
  - 4-5-email-based-password-reset-flow.md
preExistingIssues:
  - Epic 3 v1 stories (3-1-v1 through 3-5-v1) defined in epics.md but no per-story files exist yet
  - Stories 4-1/4-2/4-3 are pre-simplification; sprint-status flags them revise-required
---

# Implementation Readiness Assessment Report

**Date:** 2026-04-29
**Project:** SafeNet

## Step 1 — Document Discovery ✅

### Artifact inventory

| Type | File | Last modified | Status |
|------|------|--------------|--------|
| PRD | `_bmad-output/prd.md` | 2026-04-29 | post-simplification |
| Architecture | `_bmad-output/architecture.md` | 2026-04-29 | post-simplification |
| Epics & Stories listing | `_bmad-output/epics.md` | 2026-04-29 | post-simplification |
| UX Spec | `_bmad-output/ux-design-specification.md` | 2026-04-29 | post-simplification |
| Sprint Change Proposal | `_bmad-output/sprint-change-proposal-2026-04-29.md` | 2026-04-29 | canonical reference |
| Sprint Status | `_bmad-output/sprint-status.yaml` | 2026-04-29 | post-simplification |
| Deferred Work | `_bmad-output/deferred-work.md` | 2026-04-29 | moot annotations applied |

### Story files

Twenty (20) per-story markdown files exist in `_bmad-output/` for stories 1-1 through 4-5. Of these:
- **Stories 1-1 through 2-5 (10 stories):** done; reflect their original scope.
- **Stories 3-1 through 3-5 (5 stories):** done but **quarantined** to `archive/v0-recovery-engine`. The story files on `main` are the v0 versions; they describe behavior that is no longer in v1 product scope.
- **Stories 4-1, 4-2, 4-3 (3 stories):** done but flagged **revise-required** — the story files describe engine-driven trigger paths that no longer exist in v1.
- **Stories 4-4, 4-5 (2 stories):** unchanged; 4-5 still in flight.
- **Stories 3-1-v1 through 3-5-v1 (5 stories):** **NOT YET DRAFTED** as per-story files. They are defined as ACs in `epics.md` only.

### Duplicates

None. Single canonical version of each artifact.

### Missing

None of the four required artifact types are missing.

### Initial flags for downstream steps

1. **Epic 3 v1 has no story files** — coverage analysis will report 5 missing story files.
2. **Stories 4-1/4-2/4-3 have stale story files** — content does not match the post-simplification ACs in `epics.md`.
3. **PRD validation report is stale** (2026-04-05) — informational; not an assessment input.

---

## Step 2 — PRD Analysis ✅

### Functional Requirements Inventory

**Total FRs visible in PRD:** 45
**Retired FR numbers (post-simplification, intentionally absent):** FR4, FR5, FR11, FR12, FR13, FR14, FR15, FR40, FR41, FR47 (10 retired)
**New FRs added in simplification:** FR51, FR52, FR53, FR54, FR55, FR56 (6 new)

#### Account & Onboarding (6 FRs)

- **FR1** — User connects Stripe via OAuth without API keys; completes one-time profile (name, company, password) before dashboard
- **FR2** — Retroactive 90-day failure scan after Stripe Connect authorization
- **FR3** — DPA acknowledgement required before any dunning email send (hard gate)
- **FR48** — Single user per account at MVP; no team invitations
- **FR49** — Profile completion (full name, company name, password) mandatory after OAuth on first login
- **FR50** — Password recovery via Stripe OAuth re-auth + email-based reset flow once Epic 4 transactional email is operational

#### Payment Failure Detection (4 FRs)

- **FR6** — Daily polling cycle for new failed payment events
- **FR7** — Classify each failed payment by Stripe decline code
- **FR8** — Display breakdown of failures by decline code category
- **FR9** — Calculate and display estimated recoverable revenue figure

#### Failed-Payments Dashboard & Recommended Emails (7 FRs — post-simplification core)

- **FR10** — Decline code → recommended dunning email type via versioned rule engine config (Update payment / Retry reminder / Final notice / no-rec for fraud)
- **FR51** — Account-level redirect link configuration; embedded as "update payment" CTA in all dunning emails (defaults to Stripe customer portal URL)
- **FR52** — Current-month failed-payments dashboard with per-row recommended email type
- **FR53** — Per-row email send (recommended OR chosen type)
- **FR54** — Multi-select bulk send (per-row recommended OR single chosen type for all selected) with confirmation dialog
- **FR55** — Manual mark-resolved (transitions subscriber to Recovered with audit note)
- **FR56** — Paid-tier custom email body editor per email type (overrides tone preset)

#### Customer Status Management (7 FRs)

- **FR16** — Four-status state machine: Active / Recovered / Passive Churn / Fraud Flagged. Transitions via daily polling AND client manual action
- **FR17** — Active → Recovered when polling detects payment success OR client marks resolved
- **FR18** — → Passive Churn when polling detects `cancelled`/`unpaid`/`paused`/`cancel_at_period_end` OR client marks churned
- **FR19** — Immediate Fraud Flagged + email recommendation suppression on fraud decline code
- **FR20** — Per-customer payment history + status detail view
- **FR21** — Manual fraud-flag resolution with reason
- **FR46** — Auto-stop recovery actions + Passive Churn graduation when subscription enters non-recoverable state

#### Notifications (7 FRs)

- **FR22** — Branded email notification on payment failure
- **FR23** — Tone selector with three presets (Professional / Friendly / Minimal)
- **FR24** — Final notice email on client trigger (per-row or bulk with type "Final notice")
- **FR25** — Recovery confirmation email on polling-detected payment success OR manual resolution
- **FR26** — Functional opt-out mechanism on every notification
- **FR27** — Suppress all future notifications post-opt-out (transactional classification preserved against client marketing opt-outs)
- **FR28** — Mid-tier sends from SafeNet-managed shared domain with client brand in From field

#### Dashboard & Analytics (6 FRs)

- **FR29** — Dashboard populated with retroactive scan data on first login (no empty state)
- **FR30** — Failures segmented by decline code, customer status, recoverable revenue
- **FR31** — Recovery analytics: recovered payments, **successful retry attempts**, notifications driving card updates ⚠️ DRIFT
- **FR32** — MoM comparison view (failure rate, recovery rate, revenue protected, Passive Churn count)
- **FR33** — Opt-in weekly digest email (off by default)
- **FR34** — Triggered onboarding email on first scan completion

#### Subscription & Billing (5 FRs)

- **FR35** — 30-day full Mid-tier trial without payment method
- **FR36** — Auto-downgrade to Free post-trial; polling drops to twice-monthly
- **FR37** — Free-tier dashboard shows time-to-next-scan
- **FR38** — Monthly Mid-tier "SafeNet saved you €X" email
- **FR39** — Single upgrade CTA anchored to estimated recoverable revenue figure

#### Operator Administration (4 FRs)

- **FR42** — Operator can manually advance customer status with recorded reason
- **FR43** — Append-only audit log of every engine action (timestamp, actor, outcome)
- **FR44** — Operator full audit log view per customer/account
- **FR45** — Operator console authentication-gated; not exposed to clients

### Non-Functional Requirements Inventory

**Total NFRs:** 21

#### Security (6)

- **NFR-S1** — Stripe OAuth tokens AES-256 at rest; encryption key in env secrets only
- **NFR-S2** — TLS 1.2 minimum in transit
- **NFR-S3** — Zero raw cardholder data
- **NFR-S4** — Operator console authentication-gated
- **NFR-S5** — Tenant-scoped queries enforced at application layer
- **NFR-S6** — Confirmed security incident → 4-hour hotfix SLA

#### Reliability (5)

- **NFR-R1** — Daily polling cadence (24h ±2h); missed-poll alert within 30h
- **NFR-R2** — Marc-triggered email dispatch reaches Resend within 5s
- **NFR-R3** — Every engine action either succeeds or logs failure with reason (zero silent failures)
- **NFR-R4** — ≥99.5% monthly uptime
- **NFR-R5** — Dead-letter queue for failed jobs (no silent drops)

#### Performance (4)

- **NFR-P1** — Dashboard loads <3s for accounts up to 500 end-customers
- **NFR-P2** — 90-day retroactive scan runs as background job (never blocks UI)
- **NFR-P3** — First scan data visible <5min post-OAuth
- **NFR-P4** — Polling retries on rate-limit without hard failure

#### Scalability (3)

- **NFR-SC1** — MVP supports ≤100 connected client accounts
- **NFR-SC2** — Polling handles ≤10,000 payment events per account per cycle
- **NFR-SC3** — Data model supports multi-user account expansion without schema migration

#### Data Retention (3)

- **NFR-D1** — Event metadata retained 24 months then auto-purged
- **NFR-D2** — Audit logs retained 36 months
- **NFR-D3** — End-customer email purged within 30 days of Passive Churn (unless retained for win-back)

### PRD Completeness Assessment

The PRD is **substantially complete** for v1 implementation, but contains **pre-existing drift** — sections that did not get fully updated during the 2026-04-29 simplification edits. These reference retired concepts (engine retry, mode toggle, hourly polling) and must be reconciled before downstream artifacts can be considered fully coherent with the PRD.

#### Drift Findings (require PRD edit)

| ID | Location | Drift | Required correction |
|----|----------|-------|---------------------|
| D-PRD-1 | Line 377 — "Implementation Considerations" | "Celery + Redis for the **hourly polling job and retry execution**" | "daily polling job" + remove "retry execution" (no retry mechanism in v1) |
| D-PRD-2 | Line 400 — "Core user journeys fully supported" | "Journey 4: Operator override panel → **manual retry cancellation** → audit trail" | Replace with: "Journey 4: Operator audit log spot-check → manual status advancement" (matches updated Journey 4 narrative on lines 216–229) |
| D-PRD-3 | Line 410 — Must-have capabilities table | Row: "Payday-aware retry calendar \| Primary `insufficient_funds` differentiator" | DELETE row — retry mechanism is retired |
| D-PRD-4 | Line 413 — Must-have capabilities table | Row: "Supervised / Autopilot toggle \| Liability and trust" | REPLACE with: "DPA gate + per-row send authorization \| Liability — every email send is an explicit client action" |
| D-PRD-5 | Line 425 — Risk Mitigation table | "unknown codes route to **fixed-delay retry + notify**" | "unknown codes route to **notify-only with conservative recommended type**" |
| D-PRD-6 | Line 429 — Risk Mitigation table | "Operator email alert if no poll in **90 minutes**" | "if no poll in **30 hours**" (align with NFR-R1) |
| D-PRD-7 | Line 431 — Risk Mitigation table | Row: "Railway downtime during scheduled retry window \| ... Celery retries with jitter on infrastructure failure. Missed retry flagged in audit log." | REPLACE with: "Railway downtime during polling window \| Celery beat reschedules missed polling tick; missed-poll surface via NFR-R1 alerting" |
| D-PRD-8 | FR31 (line 515) | "successful **retry attempts**" | "**polling-detected paid-on-retry events**" or "**Stripe-side recoveries observed via daily polling**" |

#### Coverage of v1 Functional Surface

All v1 product surface area defined by the simplification proposal IS covered by the FR list:

- ✅ Stripe Connect OAuth + profile completion (FR1, FR49)
- ✅ DPA hard gate (FR3)
- ✅ Daily polling + decline-code classification (FR6, FR7)
- ✅ 90-day retroactive scan (FR2)
- ✅ Decline-code → recommended email mapping (FR10)
- ✅ Redirect link configuration (FR51) — *new in simplification*
- ✅ Current-month failed-payments dashboard (FR52) — *new*
- ✅ Per-row send (FR53), bulk send (FR54), manual resolve (FR55) — *new*
- ✅ Custom email body for paid tiers (FR56) — *new*
- ✅ Four-status FSM (FR16–19, FR46)
- ✅ Tone presets (FR23), opt-out (FR26, FR27), recovery confirmation (FR25), final notice (FR24)
- ✅ Operator audit log + manual advancement (FR42–45)
- ✅ Trial mechanics + tier degradation (FR35–39)
- ✅ Email-based password reset (FR50)

#### Coverage Gaps Found

None. All v1 capabilities described in the sprint change proposal are covered by FRs.

#### Verdict

PRD has substantive coverage for the v1 simplified surface, but **8 drift items must be reconciled** by editing the PRD itself. These are not story-level concerns — they are PRD-internal inconsistencies introduced by incomplete propagation of the 2026-04-29 simplification edits into the "MVP Feature Set," "Implementation Considerations," and "Risk Mitigation" sections.

---

## Step 3 — Epic Coverage Validation ✅

### Coverage Matrix (Post-Simplification)

| FR | PRD requirement (summary) | Epic / Story | Status |
|----|--------------------------|--------------|--------|
| FR1 | Stripe Connect OAuth (no API keys) + profile completion | Epic 2 / 2.1 + 2.1b | ✓ Covered |
| FR2 | 90-day retroactive scan | Epic 2 / 2.2 | ✓ Covered |
| FR3 | DPA hard-gate before any dunning email send | Epic 3 v1 / 3.1 (v1) | ✓ Covered |
| FR6 | Daily polling failure detection | Epic 2 / 2.2 + Epic 3 v1 / 3.4 (v1) polling task | ✓ Covered |
| FR7 | Decline-code classification | Epic 2 / 2.2 + Epic 1 / 1.3 | ✓ Covered |
| FR8 | Failure breakdown by decline code | Epic 2 / 2.4 | ✓ Covered |
| FR9 | Estimated recoverable revenue KPI | Epic 2 / 2.4 | ✓ Covered |
| FR10 | Decline code → recommended email type via rule engine | Epic 3 v1 / 3.5 (v1) | ✓ Covered |
| FR16 | Four-status state machine (polling + manual transitions) | Epic 3 v1 / 3.3 (v1) + 3.4 (v1) | ✓ Covered |
| FR17 | Active → Recovered (polling OR manual resolve) | Epic 3 v1 / 3.3 (v1) + 3.4 (v1) | ✓ Covered |
| FR18 | → Passive Churn (polling cancel/unpaid/paused) | Epic 3 v1 / 3.4 (v1) | ✓ Covered |
| FR19 | Fraud Flagged + email recommendation suppression | Epic 3 v1 / 3.2 (v1) + 3.5 (v1) | ✓ Covered |
| FR20 | Per-customer payment history + status detail | Epic 5 / 5.1 | ✓ Covered |
| FR21 | Manual fraud-flag resolution with reason | Epic 5 / 5.1 | ✓ Covered |
| FR22 | Branded failure notification email | Epic 4 / 4.1 | ✓ Covered |
| FR23 | Tone selector (3 presets) | Epic 4 / 4.2 | ✓ Covered |
| FR24 | Final notice email (client-triggered) | Epic 4 / 4.3 | ✓ Covered |
| FR25 | Recovery confirmation email | Epic 4 / 4.3 | ✓ Covered |
| FR26 | Functional opt-out mechanism | Epic 4 / 4.4 | ✓ Covered |
| FR27 | Opt-out suppression + transactional classification | Epic 4 / 4.4 | ✓ Covered |
| FR28 | SafeNet-managed shared sending domain | Epic 4 / 4.1 | ✓ Covered |
| FR29 | Dashboard populated on first login | Epic 2 / 2.4 | ✓ Covered |
| FR30 | Failures segmented by code/status/revenue | Epic 2 / 2.4 | ✓ Covered |
| FR31 | Recovery analytics ⚠️ (text drift on "retry attempts") | Epic 5 / 5.2 | ✓ Covered (drift in PRD text) |
| FR32 | MoM comparison view | Epic 5 / 5.2 | ✓ Covered |
| FR33 | Weekly digest email (opt-in) | Epic 5 / 5.3 (deferred-v2 per sprint-status) | ⚠️ Deferred |
| FR34 | Triggered onboarding email | Epic 2 / 2.1 + Epic 4 / 4.1 | ✓ Covered |
| FR35 | 30-day Mid-tier trial (no payment method) | Epic 2 / 2.5 | ✓ Covered |
| FR36 | Auto-downgrade to Free post-trial | Epic 2 / 2.5 | ✓ Covered |
| FR37 | Time-to-next-scan indicator | Epic 2 / 2.5 | ✓ Covered |
| FR38 | Monthly "SafeNet saved you" email | Epic 5 / 5.3 | ✓ Covered |
| FR39 | Upgrade CTA anchored to recoverable revenue | Epic 2 / 2.5 | ✓ Covered |
| FR42 | Operator manual status advancement | Epic 6 / 6.x | ✓ Covered |
| FR43 | Append-only audit log | Epic 1 / 1.2 + Epic 6 | ✓ Covered |
| FR44 | Operator audit log view | Epic 6 / 6.x | ✓ Covered |
| FR45 | Operator console authentication-gated | Epic 1 / 1.2 + Epic 6 | ✓ Covered |
| FR46 | Subscription cancellation → Passive Churn | Epic 3 v1 / 3.4 (v1) | ✓ Covered |
| FR48 | Single-owner account | Epic 2 / 2.1 | ✓ Covered |
| FR49 | Profile completion mandatory | Epic 2 / 2.1b | ✓ Covered |
| FR50 | Password reset flow | Epic 4 / 4.5 | ✓ Covered |
| FR51 | Account-level redirect link configuration | Epic 4 / 4.2 | ✓ Covered |
| FR52 | Current-month failed-payments dashboard | Epic 3 v1 / 3.2 (v1) | ✓ Covered |
| FR53 | Per-row email send | Epic 3 v1 / 3.3 (v1) | ✓ Covered |
| FR54 | Bulk send with confirmation dialog | Epic 3 v1 / 3.4 (v1) | ✓ Covered |
| FR55 | Manual mark-resolved | Epic 3 v1 / 3.3 (v1) | ✓ Covered |
| FR56 | Paid-tier custom email body editor | Epic 4 / 4.2 | ✓ Covered |

### Coverage Statistics

- **Total v1 PRD FRs:** 45
- **FRs covered in v1 epics:** 44 fully covered, 1 deferred-v2 (FR33 weekly digest)
- **Coverage percentage:** 100% (44/44 active v1 FRs) — FR33 was deferred per sprint-status
- **Retired FR numbers (intentionally absent — quarantined to v0 archive):** FR4, FR5, FR11, FR12, FR13, FR14, FR15, FR40, FR41, FR47

### Drift Findings — epics.md Internal Inconsistency

The epics.md file has **TWO coexisting representations** of the FR landscape, only one of which was updated in the 2026-04-29 simplification:

#### D-EPICS-1: Stale "Requirements Inventory" section (lines 17-67) — ✅ RESOLVED 2026-04-29
The top-of-document FR list still describes **pre-simplification** semantics:
- FR3 still says "before the **recovery engine** is activated" (should be "before any dunning email is sent")
- FR4, FR5 (mode selection) still listed — should be retired
- FR6 still says "**hourly** polling cycle" (should be "daily")
- FR11-15 (retry calendar, retry caps, geo-block, supervised, autopilot) still listed — should be retired
- FR17 still says "transition... when **a retry succeeds**" (should be "when polling detects payment success or client marks resolved")
- FR18 still says "transition... when **the retry cap is exhausted**" (should be "when polling detects subscription cancelled/unpaid/paused or client marks churned")
- FR24 still says "on **the last retry attempt**" (should be "when client triggers final-notice send")
- FR25 still says "when **a retry succeeds**" (should be "when polling detects payment success or client marks resolved")
- FR40, FR41, FR47 still listed — should be retired
- **FR49–FR56 are entirely missing** from the inventory — only the FR Coverage Map (Epic List) and Epic sections reference them

**Required correction:** Replace lines 17–67 with the post-simplification FR list from the PRD (lines 463–533 of prd.md).

#### D-EPICS-2: Stale "FR Coverage Map" table (lines 137-186) — ✅ RESOLVED 2026-04-29
The FR Coverage Map table still has rows for FR4, FR5, FR11–15, FR40, FR41, FR47 — and is **missing** rows for FR49, FR50, FR51, FR52, FR53, FR54, FR55, FR56.

**Required correction:** Remove retired-FR rows (FR4, FR5, FR11–15, FR40, FR41, FR47) and add rows for the 8 new FRs (FR49–FR56) with their epic mappings.

#### D-EPICS-3: Stale NFR text in Requirements Inventory (lines 76) — ✅ RESOLVED 2026-04-29 (also fixed NFR-R2 same drift class)
NFR-R1 still says "**hourly** polling job executes every **60 minutes** (±**5 minutes** tolerance); a missed cycle triggers an operator alert within **90 minutes**" — should match PRD's daily polling (24h ±2h, alert <30h).

**Required correction:** Replace NFR-R1 text with PRD line 548 wording.

### Coverage Verdict

✅ **Functional surface is fully covered** in the v1 epics — every active FR has a clearly identified epic + story. No gaps in implementable scope.

⚠️ **epics.md is internally inconsistent** — the top-of-document inventory and FR Coverage Map are stale (pre-simplification), while the Epic List + Epic 3 v1 sections + Epic 4 sections are post-simplification. This is a documentation-quality issue, not a coverage gap. **Future readers will get conflicting information depending on which section they read.**

This must be reconciled before drafting per-story files for Epic 3 v1 (CE skill output), so the stories don't inherit stale FR text.

---

## Step 4 — UX Alignment ✅

### UX Document Status

**Found.** `_bmad-output/ux-design-specification.md` exists (1,292 lines), post-simplification edited 2026-04-29.

### UX ↔ PRD Alignment

The UX spec was extensively edited during the 2026-04-29 simplification:
- ✅ Operator persona: removed "override capability"; added "audit trail access, manual status advancement, Django admin oversight"
- ✅ UX Principle 4 replaced "Mode clarity" with "Per-row clarity over engine clarity"
- ✅ "Supervised Mode" subsection replaced with "Daily Failed-Payments Review"
- ✅ Onboarding: 7-step sequence; DPA before first email send (not engine activation) — line 652 explicit: *"DPA gate sits before email send, not before any 'engine activation' — there is no engine in v1"*
- ✅ Journey 1 mode-selection nodes removed
- ✅ Journey 3 reframed as "Daily Failed-Payments Review" (line 694)
- ✅ Journey 4 replaced with "Manual Resolve" (mark-resolved + audit note)
- ✅ Sophie journey relocated to Journey 5; retry mechanics removed
- ✅ BatchActionToolbar reframed: "Send recommended (N)" / "Send specific…" / "Mark resolved" / "Exclude" (line 354)
- ✅ Added `RedirectLinkInput` (FR51) and `CustomBodyEditor` (FR56) custom components (lines 355–356)
- ✅ Renamed `EngineStatusIndicator` → `PollingStatusIndicator` (line 911, table 1009)
- ✅ Replaced "Autopilot Activation" + "Supervised Review Queue" mechanics with "First Email Send (DPA Gate)" + "Daily Failed-Payments Review"
- ✅ Updated zero-state copy: *"No failed payments this month. Your subscribers are paying — keep shipping."*

**FR coverage in UX spec:**
- FR51 (redirect link) → `RedirectLinkInput` component ✅
- FR52 (current-month dashboard) → "Daily Failed-Payments Review" journey ✅
- FR53 (per-row send) → BatchActionToolbar + per-row dropdown ✅
- FR54 (bulk send) → BatchActionToolbar primary action ✅
- FR55 (manual resolve) → BatchActionToolbar "Mark resolved" ✅
- FR56 (custom body) → `CustomBodyEditor` component ✅

### UX ↔ Architecture Alignment

The architecture (`architecture.md`) was updated in lockstep with UX:
- ✅ FR coverage map updated (FR4/5, FR11–15, FR40/41, FR47 retired; FR51–56 added)
- ✅ `engine/compliance.py` compliance gate removed; DPA gate (pre-email) added to cross-cutting concerns
- ✅ "Hourly polling" data flow replaced with "Daily polling" + "Client-initiated email send" blocks
- ✅ Requirements Coverage Validation language updated to reflect retired/added FRs

The data model + API contracts implied by FR51 (account.redirect_link), FR52 (failed-payments query filtered by month), FR53/54 (send-email + batch-send-email endpoints), FR55 (manual-resolve transition), FR56 (custom_body per email type) are addressable within the existing Django + DRF + Celery architecture without structural changes.

### Drift Findings (UX-side)

| ID | Location | Drift | Required correction |
|----|----------|-------|---------------------|
| D-UX-1 ✅ RESOLVED 2026-04-29 | Line 310 — CTA Rationale | CTA copy now: "Sign DPA to enable sends" / "Send recommended emails" | — |
| D-UX-2 ✅ RESOLVED 2026-04-29 | Line 351 — Components inventory | Renamed to `PollingStatusIndicator` with "polling cadence, last scan, next scan ETA" copy (per NFR-R1) | — |
| D-UX-3 ✅ RESOLVED 2026-04-29 | epics.md lines 116–133 — UX-DR list (cross-doc) | UX-DR5/8/15/16 rewritten in epics.md to match v1 (PollingStatusIndicator, Send recommended/specific/Mark resolved/Exclude, DPA gate before any send, current-month failed-payments list) | — |

### Warnings

⚠️ **No standalone UX warnings** — UX spec is internally coherent post-edit.

⚠️ **The UX-DR catalog in epics.md (D-UX-3 above) is stale** — when CE drafts Epic 3 v1 per-story files, it will pull from this stale UX-DR list and re-introduce removed concepts. Must be reconciled in the same epics.md cleanup pass as D-EPICS-1 and D-EPICS-2.

### UX Verdict

✅ **UX spec is coherent with PRD and architecture for the v1 simplified scope.**

⚠️ Two minor drift strings (D-UX-1, D-UX-2) in the UX spec itself, plus one stale cross-doc reference (D-UX-3 in epics.md) — all narrow text edits, no structural rework needed.

---

## Step 5 — Epic Quality Review ✅

### Epic Structure Assessment

| Epic | Title framing | User value? | Independence | Verdict |
|------|---------------|-------------|--------------|---------|
| Epic 1 | "Project Foundation & Deployable Skeleton" | Foundation (starter-template story 1.1 + tenant model 1.2 + rule engine 1.3 + frontend skeleton 1.4) | Stands alone | ✅ Acceptable for greenfield (matches bmad starter-template guidance) |
| Epic 2 | "Founder Onboarding & Free Tier Dashboard" | ✅ Strong — connect Stripe, see populated 90-day landscape, upgrade path | Uses only Epic 1 output | ✅ |
| Epic 3 v0 | "Recovery Engine, Compliance & Customer Status" | QUARANTINED — out of scope | n/a | ✅ Correctly quarantined |
| Epic 3 v1 | "DPA Gate, Failed-Payments Dashboard & Email Actions" | ✅ Strong — sign DPA, review current-month failures, send dunning emails per row or in bulk | Depends on Epic 1 (engine config), Epic 2 (subscriber data, dashboard shell). Backward-only ✅ | ✅ |
| Epic 4 | "End-Customer Notification System" | ✅ Strong — branded notifications, opt-out, recovery confirmations | Backward dependency on Epic 3 v1 (send trigger) | ✅ |
| Epic 5 | "Subscriber Detail, Analytics & Retention Emails" | ✅ Subscriber drill-down, weekly digest, retention purge | Backward only | ✅ (5.3, 5.4-monthly correctly deferred-v2) |
| Epic 6 | "Operator Administration Console" | ✅ Operator audit, manual status advancement | Backward only | ✅ (6.2 correctly deferred-v2) |

### Story Quality Findings

#### 🔴 Critical Violations
**None.** All stories follow proper "As a... I want... So that..." form. All ACs use Given/When/Then BDD structure. No epic-sized stories. No circular dependencies.

#### 🟠 Major Issues

**M-QUAL-1: Story 2.1 Task 2.2 forward-dependency on Resend (Epic 4) — ✅ RESOLVED 2026-04-29 (option (a) soft-guard applied)**
- Story 2.2 AC line 486: *"And a triggered onboarding email is sent to the client (FR34)"*
- Resend integration lives in Story 4.1 (Epic 4)
- Epic 2 cannot fully ship without Epic 4 infrastructure
- **Remediation:** Either (a) add a guard "if Resend integration is available" to soften the dependency and accept that FR34 lands properly when Story 4.1 completes; or (b) move FR34 dispatch into Story 4.1's scope and have Story 2.2 only emit a domain event consumed by Epic 4. Option (a) preserves epic ordering; option (b) is structurally cleaner. **Recommend (a) — pragmatic for solo-builder cadence.**

**M-QUAL-2: Story 2.3 contains stale "Autopilot active / Supervised" copy in ACs — ✅ RESOLVED 2026-04-29**
- Lines 506–513 reference `EngineStatusIndicator` showing *"Autopilot active or Supervised + Last scan Xm ago · next in Ym"*
- Post-simplification: there is no Autopilot/Supervised mode. The component was renamed `PollingStatusIndicator` in the UX spec.
- Also references "Review Queue when in Supervised mode" navigation tab (line 507).
- **Remediation:** Rewrite Story 2.3 ACs to use `PollingStatusIndicator` showing *"Last scan Xh ago · next scan in Yh"* with states Active / Paused / Error. Remove "Review Queue" nav tab.

**M-QUAL-3: Story 2.4 stale CTA copy — ✅ RESOLVED 2026-04-29**
- AC line 550: *"Activate recovery engine — €29/month"* — pre-simplification CTA copy
- **Remediation:** Replace with the post-simplification CTA copy from sprint change proposal (e.g., "Send your first dunning email — €29/month" or align with the wording chosen during PRD edit pass).

#### 🟡 Minor Concerns

**N-QUAL-1: Epic 3 v1 stories lack per-story files**
- Stories 3.1 (v1) through 3.5 (v1) are defined as ACs in epics.md only. No per-story markdown files exist in `_bmad-output/`.
- Quality is high in the AC text — but downstream story workflows (story validation, dev-handoff) expect per-story files.
- **Remediation:** CE workflow should generate the 5 per-story files from the existing AC blocks in epics.md before any Epic 3 v1 development begins.

**N-QUAL-2: Stories 4.1 / 4.2 / 4.3 marked revise-required in sprint-status; epics.md ACs are post-simplification but per-story files are stale**
- The AC text in epics.md (lines 986–1078) IS post-simplification (correctly references FR51, FR56, the trigger-note callouts).
- The standalone story files (`4-1-resend-integration-branded-failure-notification-email.md`, etc.) are still pre-simplification per sprint-status.
- **Remediation:** Regenerate the three story files from the post-simplification AC text in epics.md. (Same workflow as N-QUAL-1.)

**N-QUAL-3: Story 5.4 hybrid scope**
- Single story bundles "Weekly Digest Email + Data Retention + (deferred) Monthly Savings Email."
- Cohesive enough for one story, but the deferred FR38 rider lives inside the AC narrative — easy to miss.
- **Remediation:** Optional — split into Story 5.4a (Weekly Digest) and Story 5.4b (Retention Purge) on next refactor. Acceptable as-is for v1.

### Database/Entity Creation Timing

✅ **Correct.** Each story creates the tables it needs:
- Story 1.2: `Account`, `User`, `StripeConnection`, `AuditLog` (foundational)
- Story 2.1: extends `User` with profile fields
- Story 2.2: `SubscriberFailure`
- Story 3.1 (v1): `DPAAcceptance`
- Story 4.1: `EmailSendLog`, `DeadLetterLog`
- Story 4.4: `NotificationOptOut`

No "create all tables upfront" violation.

### Starter Template Compliance

✅ Architecture specifies starter templates (django-admin + create-next-app). Story 1.1 explicitly *"Monorepo Initialization, Docker Compose & CI/CD Pipeline"* covers the starter setup. Story 1.4 covers the Next.js skeleton. Compliant.

### Cross-Cutting Quality Findings

The epics.md file is **internally inconsistent** between top-of-document inventories (stale) and per-epic content (post-simplification). This is the single largest quality blocker — not because any individual story is malformed, but because:

1. The Requirements Inventory (lines 17–67) advertises 8 retired FRs (FR4, FR5, FR11–15, FR40, FR41, FR47) and is missing 8 new FRs (FR49–FR56).
2. The FR Coverage Map table (lines 137–186) has the same drift.
3. The UX-DR list (lines 116–133) has 4 stale entries (UX-DR5, UX-DR8, UX-DR15, UX-DR16) referencing removed concepts.
4. NFR-R1 text (line 76) still says hourly polling.

A reader who only reads the inventories will build a pre-simplification mental model. The per-epic content corrects this — but that's the wrong order of authority.

### Quality Verdict

✅ **All v1 stories pass quality criteria** — proper user-story form, BDD ACs, no critical structural violations, correct DB-creation timing.

⚠️ **3 Major issues to fix before development starts** (M-QUAL-1, M-QUAL-2, M-QUAL-3) — all in Epic 2 stories. These are text-level edits, not structural rework.

⚠️ **3 Minor concerns** (per-story files for Epic 3 v1, regeneration of 4.1/4.2/4.3 story files, optional 5.4 split).

⚠️ **Document-level inconsistency in epics.md** — top-of-document inventories are stale and conflict with per-epic content. Largest quality blocker; must be reconciled.

---

## Summary and Recommendations

### Overall Readiness Status

**🟢 READY (with caveats) — All approved-scope drift resolved as of 2026-04-29 remediation pass.**

> **Remediation pass summary (2026-04-29 evening):**
> - ✅ D-PRD-1 through D-PRD-8 — applied via EP workflow
> - ✅ D-EPICS-1, D-EPICS-2, D-EPICS-3 — applied (NFR-R2 also fixed in same scope class)
> - ✅ D-UX-1, D-UX-2, D-UX-3 — applied
> - ✅ M-QUAL-1, M-QUAL-2, M-QUAL-3 — applied
> - ✅ Epic 3 v1 story files (3-1-v1 through 3-5-v1) — skeletons created (Story + ACs from epics.md). Tasks/Subtasks blocks pending per-story SM-workflow expansion before development.
> - ✅ Stories 4.1 / 4.2 / 4.3 — banner-flagged `needs-regeneration`; canonical post-simplification ACs live in epics.md. SM-workflow regeneration pending.
>
> **Residual non-blocking drift (deferred):**
> - PRD lines 51, 262 — minor "recovery engine" framing strings (out of EP-approved scope; user explicitly skipped)
> - architecture.md lines 94, 114, 995 — general architectural framing references (separate doc-edit pass)
> - Story 2.2 line 39, Story 2.5 lines 17/21/82 — already-shipped stories with stale "hourly polling" / "engine activation" wording (low priority — implementation is what was merged; these are doc-rot in `_bmad-output/`)
>
> **Unblocking:** Story 3.1 (v1) is ready for development. Other v1 stories ready once SM expansion runs on each skeleton.

(Original verdict, retained for history: 🟠 NEEDS WORK — Documentation reconciliation required before per-story drafting / implementation continues.)

The 2026-04-29 simplification (sprint change proposal) is **architecturally sound and product-coherent** for v1, and the 9 approved recommendations have been implemented in the canonical sections (PRD Executive Summary, Journeys, FR list, NFR list; Architecture FR coverage map + cross-cutting concerns; UX Operator persona, Principles, Journeys, Components; sprint-status.yaml; deferred-work.md; quarantine branch with BRANCH_README.md). **No structural rework is required.**

However, the simplification edits did **not fully propagate** into:
1. The **PRD's MVP Feature Set + Implementation Considerations + Risk Mitigation** sections (8 drift items, see D-PRD-1..8)
2. The **epics.md Requirements Inventory + FR Coverage Map + UX-DR list + NFR-R1 text** (3 drift items, see D-EPICS-1..3, D-UX-3)
3. **3 individual stories' AC text** (Story 2.2 forward-dependency, Story 2.3 stale engine copy, Story 2.4 stale CTA copy — see M-QUAL-1..3)
4. **Two narrow strings in the UX spec itself** (line 310 and line 351 — see D-UX-1, D-UX-2)
5. **Per-story files for Epic 3 v1** (5 missing) and **stale per-story files for Stories 4.1 / 4.2 / 4.3** (3 to regenerate)

These are all **text-level edits**, no architectural rework required.

### Critical Issues Requiring Immediate Action

#### 🔴 Top priority — must be resolved before per-story files are drafted

1. **Reconcile epics.md inventories with post-simplification reality** (D-EPICS-1, D-EPICS-2, D-EPICS-3, D-UX-3 in epics.md)
   - Replace the Requirements Inventory FR list (lines 17–67) with the post-simplification PRD FR list (45 FRs, no FR4/5/11–15/40/41/47, includes FR49–56)
   - Update the FR Coverage Map table (lines 137–186): remove retired-FR rows, add 8 new rows for FR49–56
   - Rewrite UX-DR5, UX-DR8, UX-DR15, UX-DR16 in epics.md (lines 116–133)
   - Fix NFR-R1 text (line 76) to match PRD's daily-polling wording
   - **Why this is top-priority:** When CE drafts the 5 missing Epic 3 v1 story files, it pulls from these inventories. Stale inputs → stale stories.

2. **Reconcile PRD drift** (D-PRD-1 through D-PRD-8)
   - Most importantly: lines 410, 413 (must-haves table — retire "Payday-aware retry calendar" and "Supervised / Autopilot toggle"); lines 425, 429, 431 (risk mitigations referring to retries / 90-min alert window); line 400 (Journey 4 description); line 377 (hourly polling); FR31 text (retry attempts).
   - **Why:** These sections are quoted by stakeholders (and by CE/SM workflows) as authoritative.

3. **Fix Story 2.3 (M-QUAL-2) and Story 2.4 (M-QUAL-3) stale copy**
   - Story 2.3 ACs: replace `EngineStatusIndicator` / "Autopilot active" / "Supervised" / Review Queue nav-tab references with `PollingStatusIndicator` and v1 wording
   - Story 2.4 AC line 550: replace "Activate recovery engine — €29/month" CTA copy

#### 🟠 Secondary priority — must be resolved before development sprint starts

4. **Address Story 2.2 forward-dependency on Resend** (M-QUAL-1) — recommend soft-guard option (a)
5. **Generate the 5 missing Epic 3 v1 per-story files** — `3-1-v1-dpa-acceptance-gate.md` through `3-5-v1-recommended-email-mapping.md`
6. **Regenerate the 3 revise-required per-story files** for Stories 4.1, 4.2, 4.3 from the post-simplification AC text in epics.md
7. **Fix UX spec narrow strings** (D-UX-1 line 310 CTA copy; D-UX-2 line 351 EngineStatusBar → PollingStatusIndicator)

#### 🟡 Lower priority — quality of life

8. Optional split of Story 5.4 into 5.4a (Weekly Digest) + 5.4b (Retention Purge) — not required for v1

### Recommended Next Steps

In execution order:

1. **Run PM bmad-edit-prd (EP)** to apply D-PRD-1..D-PRD-8 corrections in `_bmad-output/prd.md`.
2. **Edit `_bmad-output/epics.md`** directly (no specific bmad workflow for this — manual edit) to apply D-EPICS-1..D-EPICS-3 + D-UX-3 corrections.
3. **Edit `_bmad-output/ux-design-specification.md`** directly to fix D-UX-1 and D-UX-2.
4. **Re-edit `_bmad-output/epics.md` Story 2.3 + Story 2.4 ACs** to fix M-QUAL-2 + M-QUAL-3.
5. **Address M-QUAL-1** in Story 2.2 — add the soft-guard wording.
6. **Run bmad-create-epics-and-stories (CE)** to generate the 5 missing Epic 3 v1 per-story files and regenerate the 3 revise-required Story 4.x files.
7. **Re-run IR** as a sanity check after all edits — should land at `READY` with zero drift items.
8. Begin/resume development on Story 3.1 (v1) — DPA Acceptance Gate.

### Outstanding deliverables before development resumes

| Artifact | Action | Owner |
|----------|--------|-------|
| `_bmad-output/prd.md` | 8 drift edits | PM (Edit PRD via EP skill) |
| `_bmad-output/epics.md` | Inventory + Coverage Map + UX-DR list + NFR-R1 + Story 2.3/2.4 AC edits | Manual edit (no skill workflow) |
| `_bmad-output/ux-design-specification.md` | 2 narrow string edits | Manual edit |
| `_bmad-output/3-1-v1-*.md` through `3-5-v1-*.md` | 5 new per-story files | CE skill |
| `_bmad-output/4-1-*.md`, `4-2-*.md`, `4-3-*.md` | Regenerate (stale, revise-required) | CE skill |

### Final Note

This assessment identified **17 actionable findings** across **5 categories** (PRD drift: 8; epics.md inventory drift: 4; story AC drift: 3; UX spec drift: 2; missing or stale story files: 8). All findings are **text-level edits**; no architectural rework is required.

The product simplification itself is sound — what remains is **finishing the propagation of the 2026-04-29 edits into the trailing sections of each artifact**. After the listed corrections, the project is positioned to resume implementation with full coherence across PRD ↔ Architecture ↔ UX ↔ Epics ↔ Stories.

---

**Assessment date:** 2026-04-29
**Assessor:** John (PM persona) via bmad-check-implementation-readiness workflow
**Project:** SafeNet
**Status:** 🟠 NEEDS WORK — reconcile drift items above, then re-run IR

