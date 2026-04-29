---
date: 2026-04-29
triggered_by: Founder strategic scope reduction (Sabri)
proposed_by: John (PM)
scope_classification: Major — fundamental replan of Epic 3, edits across PRD, Architecture, UX, Epics 4–6
mode: Batch
---

# Sprint Change Proposal — SafeNet v1 Scope Simplification

## TL;DR

SafeNet v1 becomes a **failed-payments dashboard with one-click decline-code-aware dunning emails**. The autonomous recovery engine (Autopilot/Supervised modes, automated retries, payday-aware scheduler, geo-block enforcement, FSM-driven actions, card-update triggered retries) is **quarantined to a dedicated branch** for v2. The pillar shifts from *"automation that runs without you"* to *"visibility on failures + the right email at the right time, with one click."*

**Three structural changes:**
1. **Remove the retry mechanism entirely.** SafeNet sends emails — it never charges cards.
2. **Remove Autopilot vs. Supervised duality.** Marc opens his dashboard, sees the current-month failed-payment list, and picks an action (recommended or chosen) per row.
3. **Daily polling** (not hourly) feeds the list. The list is the product.

**Scope of merged work to quarantine:** Stories 3.1, 3.2, 3.3, 3.4, 3.5 (Epic 3 in full), plus the engine-driven trigger paths in 4.1 and 4.3. Epic 4 stories 4.2/4.4/4.5 are kept as-is with edits to 4.1/4.3 to remove their engine-driven trigger paths.

---

## 1. Issue Summary

### Problem Statement

Through Epic 3 implementation we built an autonomous recovery engine — payday-aware retry scheduler, EU/UK geo-blocking enforcement, 4-state FSM with auto-transitions on retry outcomes, Autopilot/Supervised duality with DPA-gated mode selection, supervised pending-action queue with batch approval, card-update detection triggering immediate retries, and the supporting Stripe `PaymentIntent.confirm` machinery. It works. It is also far more than v1 needs.

The founder's market hypothesis is now sharpened:

> **The product is visibility on failed payments, plus a decline-code-aware dunning email Marc sends in one click.**

Everything else — automated retries, mode selection, supervised approval queues, payday-aware scheduling, geo-block enforcement on retries (no retries, no need), card-update triggered retries, engine-driven email auto-fire — is v2 territory. Building it earned us the architecture and the rule engine; running it in v1 buys complexity we cannot validate yet.

### Discovery Context

This is a **strategic founder decision**, not a technical limitation. The trigger is post-implementation reflection: complexity has scaled past what's needed to validate the core thesis (decline-code-aware dunning beats generic dunning) with first paying clients.

### Evidence

- 5 stories merged in Epic 3 implementing the autonomous engine (commits: `1c7a131`, `f516e92`, `2ed02f5`, etc. on main)
- `deferred-work.md` accumulates 60+ items, the majority concerning retry-engine edge cases (N+1 Stripe calls in `_check_subscription_cancellations`, race conditions in `_safe_transition`, `cancel_at_period_end` premature transitions, payday-window UTC drift, retry-cap mid-flight changes, etc.) — none of these matter if there is no retry engine
- Stories 4.1 and 4.3 trigger paths are wired to FSM transitions (`_safe_transition`) and engine retry events (`is_last_retry`) — these triggers are no longer the right design
- The PRD's Executive Summary leads with "Automated, intelligent payment recovery that runs without operator involvement — freeing founders to stay focused" — this positioning becomes false under the new scope
- Three of the four user journeys in the PRD (Journey 1 climax = "engine caught an `insufficient_funds` case, retried, succeeded — Marc hadn't thought about it once"; Journey 3 = "next hourly poll picks up the card update, retry succeeds, Sophie barely registers it"; Journey 4 = operator midnight retry override) are predicated on autonomous retry execution

### Categorization

**Issue type:** Strategic pivot. Not a technical failure, not a misunderstanding, not a stakeholder request — a deliberate narrowing of the v1 product hypothesis.

---

## 2. Impact Analysis

### 2a. Epic Impact Summary

| Epic | Status (now) | v1 disposition | Notes |
|------|--------------|----------------|-------|
| **Epic 1** — Foundation | ✅ done (4/4) | **Keep** | Story 1.3's rule engine survives; the action vocabulary reinterprets to email types |
| **Epic 2** — Onboarding & Free Dashboard | ✅ done (6/6) | **Keep** with one cadence change | Story 2.2 polling: hourly → daily. Story 2.5 trial-degradation cadence recalibrates |
| **Epic 3** — Recovery Engine | ✅ done (5/5) | **Quarantine + replace** | All 5 merged stories archived to dedicated branch; new Epic 3 redefined to "DPA Gate + Failed-Payments Dashboard + Email Actions" |
| **Epic 4** — Notifications | 🔄 in-progress (4/5 done; 4.5 in flight) | **Keep with edits** | 4.1 + 4.3 lose their engine-driven trigger paths; 4.2 expands to redirect-link + paid-tier custom-body editor; 4.4 + 4.5 unchanged |
| **Epic 5** — Subscriber Detail / Analytics / Retention | 📋 backlog | **Trim** | 5.1, 5.2, retention-purge portion of 5.4 kept; 5.3 (analytics + MoM) + monthly-savings portion of 5.4 deferred to v2 |
| **Epic 6** — Operator Console | 📋 backlog | **Trim** | 6.1 (auth) + 6.3 (audit log viewer + manual status advancement) kept; 6.2 (scheduled retry dashboard) removed (no retries to schedule) |

### 2b. Functional Requirements — Diff Summary

**Removed (10):**

| FR | Title | Why removed |
|----|-------|-------------|
| FR4 | Choose Supervised vs Autopilot mode | Modes deleted entirely |
| FR5 | Switch modes anytime | Modes deleted |
| FR11 | Payday-aware retry calendar | No retries |
| FR12 | Per-code retry caps | No retries |
| FR13 | EU/UK geo-block routing to notify-only | No retries to block — irrelevant. Geo-aware action recommendation may return in v2 |
| FR14 | Supervised pending action queue | Mode deleted; the failed-payments list itself replaces this concept |
| FR15 | Autopilot automatic execution | Mode deleted |
| FR40 | Operator scheduled-retry dashboard | No retries |
| FR41 | Operator cancel-retry | No retries |
| FR47 | Card-update triggered immediate retry | No retries |

**Modified (8):**

| FR | Change |
|----|--------|
| FR3 | DPA gate fires before *any dunning email is sent*, not before "engine activation" — engine concept removed from product surface |
| FR6 | "Hourly polling" → **"Daily polling"** |
| FR10 | "Distinct recovery rules per decline code" → **"Distinct *recommended dunning email type* per decline code"** (action set: send_email, fraud_flag, no_action) |
| FR16 | Status set unchanged (Active / Recovered / Passive Churn / Fraud Flagged) but transitions become polling-detected + Marc-initiated rather than FSM-driven by retry outcomes |
| FR17 | Active → Recovered: triggered by polling detecting paid status, or Marc marking resolved |
| FR18 | Active → Passive Churn: triggered by polling detecting `cancelled`/`unpaid`/`paused` subscription state, or Marc marking |
| FR24 | Final notice email: sent when Marc explicitly triggers a "final notice" email for a row (no more "before retry-cap-1" auto-fire) |
| FR25 | Recovery confirmation: sent when polling detects subscriber paid (or Marc marks recovered) — no FSM signal trigger |

**Added (6):**

| FR | Description |
|----|-------------|
| **FR51** | Marc can configure a redirect link in account settings; the link is embedded in all dunning emails as the subscriber's "update payment" CTA target. Defaults to the Stripe customer portal URL |
| **FR52** | Marc's dashboard shows all failed payments for the current month, with a per-row recommended email type derived from the decline code |
| **FR53** | Marc can trigger a dunning email per failed-payment row — accepting the recommended email type or choosing any of {Update payment, Retry reminder, Final notice} |
| **FR54** | Marc can multi-select failed-payment rows and trigger a bulk send — either "Send recommended per row" or "Send [chosen type] for all selected" |
| **FR55** | Marc can manually mark a failed payment as Resolved (transitions subscriber to Recovered with a manual-resolution audit note) |
| **FR56** | Paid-tier Marc can provide a custom email body per email type in account settings; the custom body overrides the tone preset for that type |

**Net FR delta:** −10 + 6 = **−4 FRs** (50 → 46), with 8 modified.

### 2c. Artifact Conflict & Adjustment Needs

| Artifact | Sections impacted | Change scope |
|----------|-------------------|--------------|
| **PRD** | Executive Summary; "What Makes This Special"; Success Criteria (User & Business & Technical); Product Scope (MVP Engine + Notifications); User Journeys 1, 2, 3, 4; Innovation & Novel Patterns; B2B Subscription Tiers; Functional Requirements (10 deletions, 8 modifications, 6 additions); Non-Functional Requirements (NFR-R1 cadence) | Substantial — see §4.1 for detailed edits |
| **Architecture** | Architecture Goals (engine line); Tech stack (Celery role narrows); Tier gates (mode-selection removed); Decline-code rule engine config (action vocabulary changes); File structure (`tasks/retry.py`, `engine/payday.py`, `engine/compliance.py` quarantined); FR coverage map; Data flow ("hourly polling → rule engine → state machine → audit trail" simplifies) | Substantial — see §4.3 |
| **UX Spec** | Personas (operator section); UX Principles (mode clarity removed); Mode Architecture (Supervised + Autopilot sections deleted); Onboarding & DPA Flow (mode selection step removed); User Flows (Onboarding, Supervised review queue, Card-update retry → all rewritten or removed); Component inventory (BatchActionToolbar reframed; AttentionBar simplified); Anti-patterns (some now apply differently) | Substantial — see §4.4 |
| **Epics** | Epic 3 fully redefined (5 v0 stories quarantined; 5 v1 stories drafted); Epic 4 stories 4.1/4.2/4.3 edited; Epic 5 trim; Epic 6 trim | Major — see §4.2 |
| **Sprint Status** | All `done` Epic 3 entries marked `quarantined-v2`; new Epic 3 v1 entries added as `backlog`; Story 4.1 + 4.3 marked `revise-required`; Epic 5/6 entries trimmed | See §4.5 |
| **Deferred Work** | All items prefixed "story-3-2", "story-3-3", "story-3-4", "story-3-5" (and the retry/engine portions of "story-4-1", "story-4-3") become moot under v1 — annotate them with "moot under 2026-04-29 simplification; revisit if quarantine branch reactivated" | See §4.6 |
| **Code (main branch)** | Epic 3 backend code (engine processor, retry tasks, payday calendar, compliance enforcement, supervised pending-action queue, FSM auto-transitions on retry outcomes, card-update detection); Epic 4 trigger paths (`_safe_transition` calls in 4.1/4.3 send paths) | Quarantine + revise — see §3.2 for branch strategy |

### 2d. Code Surface — Quarantine Map

The following modules/concepts originate in quarantined stories and must be archived (kept on the v2 branch, removed from main):

**Backend:**
- `backend/core/engine/payday.py` — payday-aware retry calendar
- `backend/core/engine/compliance.py` — geo-block enforcement (logic survives in concept; v2 may reuse)
- `backend/core/tasks/retry.py` — retry execution Celery task (entire file)
- `backend/core/services/recovery.py` — `schedule_retry`, retry-counting, `is_last_retry`, FSM-driven email triggers
- `backend/core/views/actions.py` — `batch_approve_actions`, supervised pending-action endpoints (entire flow)
- `backend/core/models` — `PendingAction` model (supervised queue concept) — **decision required:** delete migration or repurpose as audit-only "ProposedDunningEmail" record. See §3.4.
- `Subscriber.engine_mode`, `Account.engine_mode` field (and any DPA-mode-selection coupling)
- Polling job: card-update detection (`_detect_card_updates`), subscription cancellation polling (`_check_subscription_cancellations`) — **decision required:** card-update detection removed entirely; subscription-cancellation polling stays (drives Active → Passive Churn transitions in v1)
- DECLINE_RULES action vocabulary: `retry_only`, `retry_notify`, `notify_only` → reinterpret to email-type-only; `retry_cap`, `payday_aware`, `geo_block` fields become unused (but stay in config for v2 reactivation rather than ripping out)

**Frontend:**
- `frontend/src/app/(dashboard)/review-queue/page.tsx` — supervised mode review queue (entire page)
- Mode-selection screens; Autopilot/Supervised toggles in settings
- `BatchActionToolbar` with retry-action semantics → reframe as "send dunning email" toolbar in new Epic 3
- `EngineStatusIndicator`'s "Autopilot active / Supervised" copy → reframe to "Daily polling — last scan Xh ago · next in Yh" (no engine concept)
- `AttentionBar`'s "Review before next engine cycle in Xm" → reframe to "Failed payments awaiting your action"

**Tests:**
- `backend/core/tests/test_engine/test_payday.py`, `test_compliance.py`, `test_retry.py` — quarantine
- `backend/core/tests/test_tasks/test_retry.py`, `test_polling.py`'s card-update + retry-side tests — quarantine
- `backend/core/tests/test_api/test_actions.py` — batch-approve flow tests — quarantine
- The 10 pre-existing test failures noted on main (in `deferred-work.md` 2026-04-27) — re-evaluate which still apply: `test_billing_webhook` failures stay relevant; `test_dashboard::test_attention_items_isolated_by_tenant` (PendingAction null `recommended_retry_cap`) becomes moot if PendingAction is repurposed/deleted; `test_polling::test_missed_cycle_alert` stays relevant under daily polling cadence

### 2e. Technical Impact

- **1 quarantine branch creation** with selective revert on main (or selective stripping — see §3.2 for branch strategy)
- **5 new stories drafted** for replacement Epic 3
- **3 stories revised:** 2.2 (polling cadence), 2.5 (trial degradation cadence), 4.1 (trigger), 4.3 (trigger)
- **1 story expanded:** 4.2 (redirect link + custom body editor)
- **PRD, Architecture, UX, Epics** all rewritten in their affected sections
- **2 new Account model fields:** `redirect_link` (URL), `custom_email_bodies` (JSON map: email_type → body) — paid-tier-gated
- **1 new endpoint:** `POST /api/v1/subscribers/{id}/send-email/` (per-row trigger) and `POST /api/v1/subscribers/batch-send-email/` (bulk)
- **Celery beat cadence change:** hourly polling task → daily polling task

### 2f. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Quarantine branch rots and never gets reactivated | Low (this is fine) | Tag the branch with a README documenting what's there + the decision date; treat it as v2 inventory |
| Removing the retry engine breaks dashboard KPIs that count "retries fired / payments recovered automatically" | Medium | KPI semantics shift to "emails sent / payments recovered (any cause)"; dashboard story needs revision (handled in 3.2-v2 + 5.1) |
| Sending dunning emails without GDPR DPA acceptance | High | DPA gate stays — moves from "before engine activation" to "before any dunning email is sent" (FR3 modified). Hard gate preserved |
| Marc accidentally bulk-sends final-notice emails to all 23 subscribers | Medium | Per-row recommendation defaults to "Update payment" for first-time failures; bulk send requires confirm dialog with count + email type displayed |
| `PendingAction` model and migrations need careful disposition | Medium | Two paths: (a) delete table + migration; or (b) repurpose as `EmailDispatchRecord` — recommendation: option (b), see §3.4 |
| Frontend tone-selector live preview already in production refers to "subscriber will receive" content that auto-fires from engine | Low | Copy stays accurate post-edit (subscribers still receive these emails — they're just Marc-triggered now); preview infrastructure unchanged |
| 30-day trial mechanic is now harder to differentiate (no engine to "lock") | Medium | Trial gates: (a) sending dunning emails (free tier limit: 5 sends/month? or zero?); (b) custom-body editor (paid only); (c) batch-send (paid only?). **Decision required from Sabri** in §3.5 below |

---

## 3. Recommended Approach

### 3.1 Path Selected: **Hybrid (Rollback + MVP Review + Direct Adjustment)**

This is not Direct Adjustment — Epic 3 is rebuilt, not edited. It is not a clean Rollback — we keep the merged code on a v2 branch instead of deleting it. It is not solely an MVP Review — new stories are added. It is all three.

| Component | Choice |
|-----------|--------|
| Rollback (selective) | Strip Epic 3 + engine-driven trigger paths from `main`; preserve them on a dedicated branch |
| MVP Review | PRD scope reduced; FR set diffed (−10/+6/~8); architecture simplified |
| Direct Adjustment | New Epic 3 v1 stories (5) drafted; Epics 4/5/6 revised in place |

**Justification:**
- Pure Rollback would discard Epic 3 work permanently. The engine architecture, FSM design, payday calendar, geo-compliance module, supervised queue, card-update detection are all sound v2 inventory — discarding them would destroy real validated work
- Pure Direct Adjustment cannot reduce Epic 3 by editing — the entire premise (autopilot/supervised duality, retry execution) is gone
- Pure MVP Review without new stories would leave a hole where the failed-payments dashboard should be

### 3.2 Branch Strategy (recommended)

**Main branch** (v1 product):
- Revert merged Epic 3 stories selectively (engine processor, retry tasks, payday, compliance enforcement on retries, supervised queue, FSM auto-transitions on retry outcomes, card-update→retry pipeline)
- Keep DECLINE_RULES config (re-interpret action vocabulary)
- Keep Subscriber model + 4-state status enum (drop FSM auto-transitions on retry outcomes; status changes become polling-detected or Marc-initiated)
- Keep audit log infrastructure
- Keep Account/StripeConnection models
- Keep Epic 4.1/4.3 send-email service modules; rip out their engine-driven trigger paths and rewire to Marc-initiated triggers (new Epic 3 stories)

**Quarantine branch** (suggested name: `archive/v0-recovery-engine`):
- Branched from `main` at the latest commit including all Epic 3 work (i.e., the current `main` HEAD: `6fe105e`)
- Tagged with a `BRANCH_README.md` documenting:
  - The full set of features preserved here (autopilot, supervised, retry engine, payday, geo-block, card-update detection, FSM auto-transitions, supervised batch approval)
  - The 2026-04-29 decision rationale (this proposal as the canonical reference)
  - Reactivation conditions (when/why v2 might pick this up — e.g., post-100-clients, post-revenue-validation)
  - A frozen pointer to the deferred-work.md items that apply only to this branch

**Two suggested names — pick one (Sabri):**
- **Option A:** `archive/v0-recovery-engine` (semantic: "this was v0 of the engine; main is v1 of the product")
- **Option B:** `feature/v2-autonomous-engine` (semantic: "this is v2's autonomous-engine inventory")
- **Option C:** something else

Recommendation: **Option A** — `archive/v0-` makes the temporal relationship clear. v1 is what ships next; the engine is v0 of an idea we paused.

### 3.3 Effort & Timeline

- **Quarantine branch creation + selective revert on main:** Low effort (1–2 days); high precision required to avoid pulling out shared infrastructure (audit log, DECLINE_RULES, Subscriber model)
- **PRD + Architecture + UX edits:** Low effort (~1 day) — surgical edits per §4
- **5 new Epic 3 v1 stories drafted in epics.md:** Low effort (~0.5 day, leveraging this proposal)
- **Epic 4 story revisions (4.1, 4.2, 4.3):** Medium effort (~1–2 days) — 4.1/4.3 need trigger-path rewires; 4.2 needs new redirect-link + custom-body editor scope
- **Story 2.2 + 2.5 polling cadence revisions:** Low effort (~0.5 day)
- **Net implementation effort:** ~4–6 days for proposal application; new Epic 3 v1 stories then enter dev queue

### 3.4 PendingAction Model Decision

Two viable paths:

**Path A — Delete:** Drop `PendingAction` table via reverse migration. Cleanest. But the model captures "decline code → recommended action" which v1 still needs (just under a different name).

**Path B — Repurpose** *(recommended)*: Rename `PendingAction` → `EmailDispatchRecord` (or `DunningEmailLog`). Repurpose fields:
- `recommended_action` → `recommended_email_type` (enum: update_payment, retry_reminder, final_notice)
- `recommended_retry_cap` → drop column via migration
- Track per-failure email send history (which email type sent, when, by whom)

Path B avoids losing the "recommendation per failure" data we already polulate, and it gives 4.4 (opt-out) + 5.x (subscriber detail timeline) a natural place to read email send history from. Architecture call: **recommend Path B**, but flag for Winston (architect) review before commit.

### 3.5 Open Decisions Requiring Sabri's Input

| # | Decision | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | Quarantine branch name | A/B/C above | A: `archive/v0-recovery-engine` |
| 2 | PendingAction disposition | Delete vs Repurpose | Repurpose as `EmailDispatchRecord` |
| 3 | Free tier email-send limit | (a) Free can send unlimited emails; (b) Free can view list only, paid required to send any email; (c) Free gets N free sends/month | **(b) — view-only Free tier.** Sending is the core paid action. Reinforces upgrade trigger |
| 4 | Custom email body availability | Paid only (any tier) vs Pro only | Per founder direction: "in the paid tiers" — interpret as **Mid + Pro both get it** |
| 5 | Bulk send availability | Free vs paid only | Paid only — bulk send is the high-leverage operator move |
| 6 | Recommended-email logic for repeat failures | Always recommend "Update payment"; or escalate over time (Update → Retry reminder → Final notice based on days since failure) | **Time-based escalation:** day 0 = Update payment, day 7+ = Retry reminder, day 14+ = Final notice. Marc can always override |
| 7 | Subscription-cancellation polling (drives Active → Passive Churn) | Keep vs remove | **Keep.** It's polling-detected, not retry-driven; it's the only honest way to know when to stop emailing |
| 8 | Recovery-detection on polling (subscriber paid via own initiative) | Keep vs remove | **Keep.** Drives Active → Recovered transition + recovery confirmation email |
| 9 | Card-update detection in polling | Keep (drives recommendation: "subscriber updated their card → consider Update payment email") vs remove | **Remove for v1.** It only mattered as a retry trigger; without retries, low value. Quarantine to v2 |

I'll wait for your input on these 9 before applying any artifact edits.

---

## 4. Detailed Change Proposals

### 4.1 PRD Edits (`_bmad-output/prd.md`)

#### Edit 1 — Executive Summary (lines 25–43)

**OLD (line 31):**
> **Primary value:** Automated, intelligent payment recovery that runs without operator involvement — freeing founders to stay focused on product and growth rather than operational fire-fighting.

**NEW:**
> **Primary value:** Visibility on every failed payment, plus the right decline-code-aware dunning email Marc sends in one click. SafeNet diagnoses the failure; Marc decides what to send; the email goes out reflecting his brand voice.

**OLD (line 33):**
> **Business model:** Three-tier freemium. Free tier delivers a genuine diagnostic dashboard (90-day retroactive scan, failure landscape, estimated recoverable revenue) — no actions fire, no paywall. Mid tier activates the recovery engine: code-aware retries, tone-selector notifications, GDPR-compliant flows. Pro tier (post-MVP) adds white-label notifications, AI-assisted copy, and passive churn export. 30-day full mid-tier trial; post-trial degradation to reduced polling frequency rather than hard paywall.

**NEW:**
> **Business model:** Three-tier freemium. Free tier delivers a genuine diagnostic dashboard (90-day retroactive scan, current-month failed-payments list, failure landscape KPIs, estimated recoverable revenue) — view-only, no email sends. Mid tier activates email sending: per-row & batch dunning emails, three tone presets (Professional / Friendly / Minimal), redirect-link configuration, GDPR-compliant flows including DPA gate. Pro tier (post-MVP) adds custom email bodies per email type, white-label sending domain, AI-assisted copy. 30-day full Mid-tier trial; post-trial degradation to view-only Free.

**OLD (lines 36–43, "What Makes This Special" — three sub-sections):**
Currently emphasizes diagnosis-before-action, compliance-as-architecture, free-tier-as-ROI-calculator, *and* "constrained action set as trust signal" with "exactly two things: retry the original payment amount, or notify the end customer."

**NEW (replace the "Constrained action set" sub-section):**
> **One action, three voices.** SafeNet does exactly one thing to the end-customer: send a decline-code-appropriate dunning email reflecting the founder's chosen tone. No retries, no charges, no silent plan downgrades. The constraint is the trust signal — Marc retains full control of what subscribers hear.

#### Edit 2 — Success Criteria (lines 53–86)

**REMOVE these targets:**
- "Zero operational involvement: A successfully onboarded Mid-tier user runs SafeNet entirely on autopilot. No manual actions required after initial setup. Recovery happens without the founder's attention." (line 58) — *the entire premise has changed; v1 expects Marc to engage daily/weekly with the failed-payments list*
- "100% scheduled retry execution. Every retry queued by the rule engine fires within its scheduled window." (line 75)
- "Recovery rate for `insufficient_funds` failures: target ≥40% of payday-aware retries succeed" (line 84)

**ADD these targets:**
- **Time-to-first-email:** Within 90 seconds of opening the dashboard for the first time (post-DPA), Marc can send his first dunning email — recommended action pre-selected, one click to dispatch.
- **Email-driven recovery rate:** target ≥25% of dunning emails sent result in subscriber-initiated payment update + paid-on-retry-by-Stripe-natively within 14 days.
- **Email send reliability:** ≥99.5% of Marc-triggered email sends reach Resend successfully on first attempt.

#### Edit 3 — Product Scope > MVP (lines 90–124)

**REMOVE entire "Engine" subsection lines 92–101** (Stripe Connect OAuth survives — move to "Onboarding & Detection"). Specifically remove:
- Bounded retry with code-dependent caps
- Payday-aware retry calendar for `insufficient_funds`
- Geo-aware compliance layer
- Supervised mode / Autopilot toggle
- Internal admin override panel (operator-facing)

**REPLACE with new "Onboarding & Detection" subsection:**
```
- Stripe Express Connect OAuth onboarding (zero API key handling)
- Daily polling-based failure detection
- 30+ decline-code mapper: each code → recommended dunning email type
- Polling-detected status transitions: Active → Recovered (subscriber paid) / Passive Churn (subscription cancelled, paused, or unpaid)
- Fraud flagging on `fraudulent` decline code: stops automatic recommendations; surfaces for manual review
```

**ADD new subsection "Failed-Payments Dashboard (Mid):" between Dashboard and Notifications:**
```
- Current-month failed-payments list, populated daily
- Per-row: subscriber name, amount, plain-language decline reason, recommended email type, status badge
- Per-row action: Send recommended email, Send specific email (Update payment / Retry reminder / Final notice), Mark resolved, Exclude from future recommendations
- Bulk select + bulk send (recommended-per-row OR single chosen type for all selected)
- Empty-state: "No failed payments this month."
```

**MODIFY "Notifications (Mid):" subsection (lines 113–117):**
- Replace "One crafted default template per notification type" with "Three crafted default templates: Update payment / Retry reminder / Final notice"
- Add "Recovery confirmation email (sent on polling-detected payment success or Marc-triggered Mark-as-resolved)"
- Add "Redirect link configurable per account; embedded in all emails as the subscriber's payment-update CTA"
- Add "(Pro/Mid paid tier) Custom email body per email type, overriding tone preset"
- Remove "Graceful final notice (last-attempt email, explicit and honest)" — reframe as one of the three default templates Marc chooses

**REMOVE "Compliance" line about geo-aware retry blocking** — replace with: "Geo-aware compliance: SEPA/UK direct-debit context surfaced as a warning on the failed-payment row (hint to Marc that automated retry would be illegal); no automated retries to block in v1."

#### Edit 4 — User Journeys (lines 154–225)

**Journey 1 (Marc onboarding) — RESTRUCTURE climax + resolution:**

OLD climax (lines 165–167): Engine catches `insufficient_funds`, retries, succeeds, Marc gets "Payment recovered — €89" email without lifting a finger.

NEW climax: Day 7. Marc opens the dashboard for his weekly review. 4 new failures since last visit. Three are `insufficient_funds` — recommended email: Update payment. One is `card_expired` — recommended: Update payment. He reviews each row's decline reason, accepts the recommendations, clicks "Send recommended (4)". Resend confirmations land on the four subscribers' inboxes within seconds. Marc closes the tab.

Day 21. Marc gets a recovery confirmation summary email from SafeNet: "3 of your 4 dunning emails this fortnight resulted in successful payment. €234 recovered." The fourth subscriber's status is now Passive Churn (subscription cancelled). Marc upgrades to Mid before trial expires.

**Journey 3 (End-customer Sophie) — MINOR EDIT:**

The narrative still works (Sophie gets a card-update email, updates her card, gets a confirmation). The only edit: remove the line "The next hourly poll picks up the card update. SafeNet queues an immediate retry. It succeeds." Replace with: "Stripe processes the payment automatically against her new card on the next billing cycle. The next daily poll detects the success. SafeNet sends the recovery confirmation email."

**Journey 4 (Operator midnight override) — REMOVE ENTIRELY.** No retries to override. The operator role narrows to: (a) audit log review, (b) Django admin oversight, (c) manual status advancement on edge cases. Replace Journey 4 with a shorter Journey 4: *"The Operator — Audit Log Spot-Check"* describing the operator reviewing audit logs to confirm a Marc complaint that "an email never sent" — operator finds the Resend dead-letter entry, identifies bouncing domain, advises Marc.

**Journey 2 (Fraud flag) — MINOR EDIT:** The fraud-flag logic is unchanged; SafeNet still surfaces fraud-flagged subscribers without any automated action. Edit only the line "SafeNet did nothing — no retry, no email" → "SafeNet did nothing — no email recommendation, just the flag."

**Journey Requirements Summary table (line 228):** Remove rows: "Autopilot / Supervised mode toggle"; "Payday-aware retry execution"; "Card-update CTA + GDPR opt-out → Recovery confirmation email; retry on card update detection" (split: keep card-update CTA + opt-out + recovery confirmation; remove "retry on card update detection"); "Internal admin override panel"; "Retry schedule visibility for operator"; "Manual status advancement" (keep — still relevant).

**Add row:** "Failed-payments list with per-row recommended email + bulk send → Journey 1"

#### Edit 5 — Innovation & Novel Patterns (lines 282–303)

**Innovation 1 — Diagnosis-First Dunning:** Stays. Now strengthened: SafeNet diagnoses the code and prescribes the *email* (not the retry strategy).

**Innovation 2 — Payday-Aware Retry Calendar:** **REMOVE entirely.** No retries. No payday calendar. v2 territory.

**Replace Innovation 2 with:**
> **One-Click Recommended Actions on a Failed-Payment List.** SafeNet inverts the dunning workflow: instead of configuring rules upfront and trusting automation, Marc opens his daily dashboard, sees a list of every failed payment, and ships a recommended email per row in one click. The cognitive load is "review the list" not "configure the engine."

**Innovation 3 — Compliance as Architecture:** Stays, with edits. Geo-aware *retry* blocking is removed (no retries to block); replace with: "DPA acceptance gates *email sending* (no email sends without DPA); GDPR transactional classification for all dunning emails; opt-out enforced before every send."

#### Edit 6 — Functional Requirements (lines 459–531)

Apply the FR diff from §2b. Specific edits:

**REMOVE entirely:**
- FR4 (line 464): "A client can choose between Supervised mode and Autopilot mode..."
- FR5 (line 465): "A client can switch between Supervised and Autopilot mode..."
- FR11 (line 480): "...schedule `insufficient_funds` retries within a 24-hour window..."
- FR12 (line 481): "...enforce a maximum retry count per failure by decline code category..."
- FR13 (line 482): "...detect EU/UK payment contexts...route them to notify-only..."
- FR14 (line 484): "In Supervised mode, SafeNet queues pending actions..."
- FR15 (line 485): "In Autopilot mode, SafeNet executes recovery actions automatically..."
- FR40 (line 526): "The SafeNet operator can view all scheduled retries..."
- FR41 (line 527): "The SafeNet operator can cancel a scheduled retry..."
- FR47 (line 483): "...detect when an end-customer updates their payment method and queue an immediate retry..."

**MODIFY:**
- FR3 (line 463): "A client must acknowledge and sign a Data Processing Agreement before **the recovery engine is activated**" → "...before **any dunning email is sent on their behalf**"
- FR6 (line 472): "...detect new failed payment events from a connected Stripe account on **an hourly polling cycle**" → "...on **a daily polling cycle**"
- FR10 (line 479): "...apply distinct recovery rules to each decline code category (retry-only, notify-only, retry+notify, no-action)" → "...map each decline code to a recommended dunning email type (Update payment / Retry reminder / Final notice / no-recommendation for fraud-flagged)"
- FR16 (line 489): keep wording but add: "...statuses are assigned by daily polling detection (paid → Recovered, cancelled → Passive Churn, fraudulent code → Fraud Flagged) and by client manual action (mark resolved → Recovered, exclude → no further recommendation)."
- FR17 (line 490): "...transition a customer from Active to Recovered when **a retry succeeds**" → "...when **the next daily poll detects payment success, or the client manually marks the failure resolved**"
- FR18 (line 491): "...transition a customer to Passive Churn when **the retry cap is exhausted without recovery**" → "...when **the daily poll detects subscription `cancelled`, `unpaid`, `paused`, or `cancel_at_period_end`, or the client manually marks the subscriber as churned**"
- FR24 (line 501): "...send a final notice email to an end-customer **on the last retry attempt**, before graduating them to Passive Churn" → "...when **the client triggers a final-notice send on a failed-payment row** (manual or via bulk action with email type 'Final notice' chosen)"
- FR25 (line 502): "...send a payment recovery confirmation email to an end-customer **when a retry succeeds**" → "...when **the next daily poll detects payment success or the client marks the failure resolved**"

**ADD (after FR50, line 469):**
- FR51: A client can configure a redirect link in their account settings; the link is embedded in all dunning emails as the subscriber's "update payment" CTA target (defaults to the Stripe customer portal URL).
- FR52: A client's dashboard shows all failed payments for the current month, with a per-row recommended email type derived from the decline code via the rule engine.
- FR53: A client can trigger a dunning email per failed-payment row — accepting the recommended email type or choosing any of {Update payment, Retry reminder, Final notice}.
- FR54: A client can multi-select failed-payment rows and trigger a bulk send — either "Send recommended per row" or "Send [chosen type] for all selected", with a confirmation dialog showing count + email types before dispatch.
- FR55: A client can manually mark a failed payment as Resolved (transitions subscriber to Recovered with a manual-resolution audit note).
- FR56: Paid-tier clients can provide a custom email body per email type in account settings; the custom body overrides the tone preset for that email type when sending.

#### Edit 7 — Non-Functional Requirements (lines 534–569)

**MODIFY NFR-R1 (line 546):** "The hourly polling job executes every 60 minutes (±5 minutes tolerance); a missed cycle triggers an operator alert within 90 minutes" → "The daily polling job executes once every 24 hours (±2 hours tolerance); a missed poll triggers an operator alert within 30 hours"

**MODIFY NFR-R2 (line 547):** "Scheduled retries fire within their designated time window with ≤15 minutes variance" → **REMOVE entirely** (no scheduled retries) → replace with: "Marc-triggered email dispatches reach Resend within 5 seconds of the trigger (synchronous queue with async dispatch)"

#### Edit 8 — Subscription Tiers (lines 339–344)

Update the table:

| Tier | Price | Features |
|------|-------|----------|
| **Free** | €0/month | Dashboard + 90-day retroactive scan + failure landscape KPIs + current-month failed-payments list (view-only). DPA gate not required (no email sends). Polling: daily during 30-day trial; drops to weekly post-trial. **No email sends.** |
| **Mid** | €29/month | Free + DPA-gated dunning email sends: per-row & bulk; three tone presets; redirect-link configuration; GDPR-compliant flows; recovery confirmation; opt-out infrastructure. Emails sent from SafeNet-managed shared sending domain (`payments.safenet.app`). |
| **Pro** | €79/month | Mid + custom email bodies per email type; white-label sending domain; AI-assisted notification copy. |

(Pro and Mid both get custom-body editor in v1 if Sabri picks "all paid tiers" in §3.5.4 above; otherwise Pro-only as listed.)

#### Edit 9 — Domain-Specific Requirements > Risk Mitigations (lines 271–280)

Remove rows: "Retry fires causing end-customer overdraft", "Retry cap exceeded without client awareness". Add: "Marc bulk-sends wrong email type to all subscribers" → "Bulk-send confirmation dialog shows per-row email type + count; per-row preview accessible from the dialog; undo within 60 seconds (Resend supports cancel within scheduling window)."

---

### 4.2 Epics Edits (`_bmad-output/epics.md`)

#### 4.2.1 — Mark Epic 3 (entire current section) as quarantined

At top of current Epic 3 section (line ~601), insert:

```markdown
> **⚠️ QUARANTINED 2026-04-29.** This epic and all 5 stories below (3.1, 3.2, 3.3, 3.4, 3.5) are preserved on branch `archive/v0-recovery-engine` and are **not in the v1 product**. Reference: `_bmad-output/sprint-change-proposal-2026-04-29.md`.
> 
> The simplified v1 Epic 3 follows immediately after this section.
```

Leave the existing Epic 3 content in place (do not delete from epics.md — it's the historical record of what got built), but visually offset it as quarantined.

#### 4.2.2 — Insert NEW Epic 3 (v1) section

After the quarantined Epic 3 ends (before "## Epic 4"), insert the new Epic 3:

```markdown
## Epic 3 (v1): DPA Gate, Failed-Payments Dashboard & Email Actions

A Mid-tier client signs the DPA, then opens their dashboard to see all current-month failed payments with a recommended dunning email per row. They click to send (single or batch), choose a different email type if they prefer, or mark a failure as resolved. Status transitions are polling-detected (Active → Recovered / Passive Churn) and Marc-initiated (manual resolve, exclude). No automated retries; no autopilot/supervised duality.

**FRs covered:** FR3, FR10, FR16, FR17, FR18, FR19, FR52, FR53, FR54, FR55
**UX-DRs covered:** UX-DR4 (simplified), UX-DR8 (reframed), UX-DR9, UX-DR10, UX-DR15

### Story 3.1 (v1): DPA Acceptance Gate

As a Mid-tier founder, I want to formally sign the Data Processing Agreement before SafeNet sends emails to my subscribers, so that I understand what SafeNet processes on my behalf and explicitly authorize the email-send capability.

[Acceptance criteria — DPA presented as full-page formal screen pre-first-email-send; sign action records DPAAcceptance with timestamp and account FK; client cannot trigger any dunning email until DPA accepted; Settings shows DPA acceptance status; existing DPA records from v0 carry over without re-acceptance.]

### Story 3.2 (v1): Current-Month Failed-Payments Dashboard

As a Mid-tier founder, I want a dashboard view of all failed payments from the current month with recommended emails per row, so that I can review and act on each at my own pace.

[Acceptance criteria — list view filtered to `failure_created_at` within current calendar month; per row: subscriber name + email, amount in cents formatted to €, plain-language decline reason via DeclineCodeExplainer, recommended email type chip, status badge (Active/Recovered/Passive Churn/Fraud Flagged), last-email-sent timestamp if any; list sortable by amount desc / date asc; view-only on Free tier (action buttons disabled with upgrade CTA); empty state for the month: "No failed payments this month."]

### Story 3.3 (v1): Per-Row Send & Manual Resolve

As a Mid-tier founder, I want to trigger a recommended (or chosen) dunning email per failed-payment row, and to manually mark failures as resolved, so that I act on each case without leaving the dashboard.

[Acceptance criteria — per-row "Send recommended" button dispatches the engine-recommended email type; per-row dropdown "Send specific email" (Update payment / Retry reminder / Final notice); per-row "Mark resolved" sets subscriber status to Recovered with manual-resolution audit note; per-row "Exclude" disables future recommendations for this subscriber; opt-out check enforced before every send; backend POST /api/v1/subscribers/{id}/send-email/ with email_type body field; rate limit per-account (10 sends/min); audit log records every send with email_type, trigger=client_manual.]

### Story 3.4 (v1): Bulk Send & Status Polling

As a Mid-tier founder, I want to bulk-send dunning emails for multiple selected rows, and trust SafeNet to detect when subscribers pay or cancel through daily polling, so that I cover the high-leverage moves quickly without micromanaging each subscriber.

[Acceptance criteria — multi-select via checkbox column; bulk action toolbar slides up on selection (UX-DR8 reframed): "Send recommended (N)" + "Send specific (chosen type)" + "Mark resolved (N)" + "Exclude (N)"; confirm dialog shows count + email types per row + total; partial failures surface per-row with toast; daily polling task: detects subscription state changes (cancelled/unpaid/paused → Passive Churn) and payment success on previously-failed PIs (→ Recovered) and dispatches recovery confirmation email; backend POST /api/v1/subscribers/batch-send-email/; same opt-out/rate-limit/audit guarantees as 3.3.]

### Story 3.5 (v1): Recommended-Email Mapping (Decline Code → Email Type)

As a developer, I want the rule engine to map each decline code to a recommended email type and time-since-failure escalation, so that the dashboard's per-row recommendation is data-driven and testable.

[Acceptance criteria — DECLINE_RULES re-interpreted: action vocabulary becomes {update_payment, retry_reminder, final_notice, fraud_flag, no_recommendation}; retry_cap, payday_aware, geo_block fields kept in config but not used in v1 (v2 reactivation-ready); time-since-failure escalation logic: day 0–6 = update_payment, day 7–13 = retry_reminder, day 14+ = final_notice; fraudulent code = fraud_flag (no recommendation); unknown codes via _default = update_payment; pure-Python module, zero DB dependency, fully pytest-able; recommendations exposed via subscriber_failure serializer field.]
```

#### 4.2.3 — Story 2.2 edit: hourly → daily polling

In Story 2.2 acceptance criteria (line ~485), change:
- "...the hourly polling job (`poll_new_failures`) is registered with Celery beat" → "...the daily polling job (`poll_new_failures`)..."
- "...When it runs every 60 minutes (±5 min tolerance)" → "...every 24 hours (±2h tolerance)"
- "...if a polling cycle is missed, an operator alert fires within 90 minutes" → "...within 30 hours"

#### 4.2.4 — Story 2.5 edit: trial degradation cadence

In Story 2.5 (line ~582), change:
- "...polling frequency drops to twice-monthly" → "...polling frequency drops to weekly"
- (rationale: with daily as new baseline, twice-monthly is too sparse; weekly preserves "you can still see new failures, just less often" framing)

Also: "the recovery engine is deactivated — no new retries or notifications are sent" → "email sending is deactivated — no new dunning emails dispatched. Free tier shows the failed-payments list view-only."

#### 4.2.5 — Story 4.1 edit: trigger path

Replace AC paragraph 1 of Story 4.1 (line ~799): "When a notification action is triggered by the engine" → "When a client triggers a dunning email send via the failed-payments dashboard (per-row or batch action)"

Add note at end of Story 4.1: "The engine-driven auto-trigger path is quarantined to `archive/v0-recovery-engine`. v1 sends are exclusively client-initiated."

#### 4.2.6 — Story 4.2 edit: expand to redirect link + custom body editor

Add new ACs to Story 4.2:

```
**Given** the Settings → Notifications screen
**When** the client views the redirect link section
**Then** an input field shows the redirect link (URL, defaults to Stripe customer portal URL)
**And** the client can edit it; on save, validation enforces https:// scheme + reachable URL pattern
**And** the link is embedded in all subsequent dunning emails as the subscriber's "update payment" CTA target (FR51)

**Given** a paid-tier (Mid or Pro) client on the Settings → Notifications screen
**When** they expand the "Custom email body" section
**Then** they see three textarea editors: Update payment / Retry reminder / Final notice
**And** each starts pre-filled with the current tone-preset's default body
**And** they can edit each independently; on save, the custom body overrides the tone preset for that email type (FR56)
**And** Free-tier clients see the editors disabled with an upgrade CTA
```

#### 4.2.7 — Story 4.3 edit: trigger path

Replace ACs in Story 4.3:
- "When the engine queues the last retry, a final notice email is sent" → "When the client triggers a 'Final notice' email type for a row (per-row or batch), a final notice email is sent (FR24)"
- "When a retry succeeds and the subscriber transitions to `recovered`, the post-transition signal fires, a recovery confirmation email is sent" → "When the daily polling job detects a previously-failed payment intent has succeeded, OR the client manually marks the failure as resolved, a recovery confirmation email is sent within the next polling cycle (FR25)"

Add note: "FSM auto-transition signal trigger is quarantined to `archive/v0-recovery-engine`."

#### 4.2.8 — Epic 5 trim

Replace Epic 5 sub-paragraph: "A client can drill into any individual subscriber's payment history, review recovery analytics and month-over-month trends, resolve fraud flags, and receive automated emails proving SafeNet's value." → "A client can drill into any individual subscriber's payment history, resolve fraud flags, receive a weekly digest, and benefit from automated retention/email purges."

**Story 5.1** (Subscriber detail panel): Keep. Edit AC: remove "all engine actions taken (retries fired, notifications sent, status changes)" → "all email send history (per email type, timestamps), status transitions, and manual notes."

**Story 5.2** (Fraud flag manual resolution): Keep unchanged.

**Story 5.3** (Recovery analytics + MoM): **Mark as deferred to v2.** Add note: "Deferred under 2026-04-29 simplification — analytics framing depended on auto-recovery engine. Reframe + reactivate when v1 has real send-volume data."

**Story 5.4** (Weekly digest + monthly savings + retention): **Split.**
- Keep weekly digest portion
- Mark monthly-savings portion as deferred to v2 ("'SafeNet recovered €X' email reframes when recovery becomes email-driven; defer 1 cycle and revisit with real data")
- Keep retention portion (event metadata 24mo + audit 36mo + email purge 30 days post-Passive-Churn)

#### 4.2.9 — Epic 6 trim

**Story 6.1** (Operator authentication): Keep unchanged.

**Story 6.2** (Scheduled retry dashboard): **Mark as quarantined to v2.** No retries to schedule. Replace with a placeholder note in the section.

**Story 6.3** (Manual status advancement + audit log viewer): Keep, with small edit to AC: remove "advance customer's status" wording referencing FSM transitions → "manually update customer status (with reason recorded in audit log) for edge cases the polling detection misses."

---

### 4.3 Architecture Edits (`_bmad-output/architecture.md`)

#### Edit 1 — Architecture Goals table (lines 30–32)

Replace:
| Account & Onboarding | 6 (FR1–5, FR48) | Stripe Connect OAuth, DPA gate, mode selection |
| Recovery Engine | 7 (FR10–15, FR47) | Rule engine, payday calendar, geo-compliance, state transitions |

With:
| Account & Onboarding | 5 (FR1–3, FR48, FR49) | Stripe Connect OAuth, DPA gate (gates email sending) |
| Failed-Payments Dashboard & Email Actions | 6 (FR10, FR52–55, FR16) | Recommended-email rule engine; per-row + bulk send; manual resolve; status display |

#### Edit 2 — Architecture Goals → Reliability (line 46)

"Hourly poll ±5 min tolerance; 90-min alert on missed cycle" → "Daily poll ±2h tolerance; 30h alert on missed cycle"

#### Edit 3 — No-real-time + batch-action notes (lines 53, 55)

"All data is polling-driven (hourly)" → "All data is polling-driven (daily)"

"Batch action (Supervised mode): API needs a bulk-action endpoint" → "Batch send action: API needs a bulk-send endpoint at `/api/v1/subscribers/batch-send-email/` — partial batch failure must be surfaced cleanly per-row."

#### Edit 4 — Compliance gates (line 98)

"DPA acknowledgement required before engine activation (hard gate)" → "DPA acknowledgement required before any dunning email is sent (hard gate)."

"EU/UK payment context checked before every retry" → **REMOVE** (no retries). Replace with: "Geo-context surfaced as a row warning on the failed-payments dashboard for SEPA/UK direct-debit failures (informational; no automated action)."

#### Edit 5 — Tier gating (line 100)

"Polling frequency, engine activation, notification sending, and Pro features all require tier checks" → "Polling frequency, email sending capability (DPA + Mid required), custom email body editor (paid required), and Pro features all require tier checks."

#### Edit 6 — Reliability & observability (line 102)

"Dead-letter queue on all Celery jobs. Polling health monitoring with 90-minute alert threshold" → "Dead-letter queue on all Celery jobs (polling, email send). Polling health monitoring with 30-hour alert threshold (daily cadence)."

#### Edit 7 — Tech stack (line 78)

"Job scheduler | Celery + Redis | Hourly polling + retry execution" → "Job scheduler | Celery + Redis | Daily polling + email send dispatch."

#### Edit 8 — DECLINE_RULES config (lines 240–251)

Replace the entire block with:

```python
DECLINE_RULES = {
    "card_expired":           {"recommended_email": "update_payment",  "fraud_flag": False},
    "insufficient_funds":     {"recommended_email": "update_payment",  "fraud_flag": False, "geo_warning": True},
    "fraudulent":             {"recommended_email": None,              "fraud_flag": True},
    "do_not_honor":           {"recommended_email": "update_payment",  "fraud_flag": False, "geo_warning": True},
    "card_velocity_exceeded": {"recommended_email": "update_payment",  "fraud_flag": False},
    # ... 30+ codes total ...
    "_default":               {"recommended_email": "update_payment",  "fraud_flag": False},
}
```

Replace explanatory paragraph: "Unknown codes fall through to `_default` — conservative, never fraud-flags. Config is version-controlled and fully testable with pytest, no DB required. The recommended_email is escalated by time-since-failure: day 0–6 = update_payment, day 7–13 = retry_reminder, day 14+ = final_notice (applied at serialization time, not in DECLINE_RULES itself, so the config remains time-agnostic)."

#### Edit 9 — File structure (lines 631–693)

**Quarantine these to `archive/v0-recovery-engine`:**
- `backend/core/engine/payday.py`
- `backend/core/engine/compliance.py` (or keep with `is_geo_blocked` function unused but ready for v2)
- `backend/core/engine/state_machine.py` — repurpose for status display only, drop FSM transitions on retry events
- `backend/core/tasks/retry.py`
- `backend/core/views/actions.py` — most contents, retain only opt-out / send-email view shells
- `backend/core/admin/retry_queue.py`

**Keep + repurpose:**
- `backend/core/engine/rules.py` — keep, action vocabulary changes
- `backend/core/engine/processor.py` — keep, returns recommended_email_type (not action)
- `backend/core/tasks/polling.py` — keep, simplified (no card-update + no retry-side, but keeps subscription-state polling + payment-success polling)
- `backend/core/services/recovery.py` — strip retry orchestration, retain manual-resolve logic
- `backend/core/services/email.py` — keep, trigger paths rewire

**Add:**
- `backend/core/views/email_dispatch.py` — per-row + batch send endpoints
- `backend/core/services/email_recommendations.py` — time-since-failure escalation logic

#### Edit 10 — Tier-gate matrix (line 807)

Replace "Retry override | ❌ Not available | ✅ Admin only" → **REMOVE row** (no retries).

Add: "Email send capability | ❌ View-only on Free | ✅ Mid+ with DPA accepted"

Add: "Custom email body editor | ❌ Free | ✅ Mid+ paid only"

#### Edit 11 — FR coverage map (lines 818–824)

Apply the FR diff. Specifically:
- Remove FR11–15, FR40, FR41, FR47 rows
- Modify FR3 row to "DPA gate before email send"
- Modify FR6 row to "daily polling" backend module
- Modify FR10 row to "engine/rules.py + engine/processor.py (recommended_email_type)"
- Add FR51–56 rows mapping to new Account fields, settings views, dashboard views, batch endpoint

#### Edit 12 — Data flow (lines 851–860)

Replace "Hourly polling: tasks/polling.py → engine/processor.py → models/subscriber.py (FSM transition) → tasks/retry.py or tasks/notifications.py (queued)" with:

```
Daily polling:
  tasks/polling.py (per active account) →
    detect new failures → engine/processor.py → recommended_email_type → SubscriberFailure row →
    detect subscription state changes (cancelled/unpaid/paused) → Subscriber.mark_passive_churn (no FSM auto-on-retry; status-change-on-detection) →
    detect previously-failed PIs now succeeded → Subscriber.mark_recovered → tasks/notifications.send_recovery_confirmation

Client-initiated email send:
  views/email_dispatch.py (per-row or batch) →
    opt-out check → tasks/notifications.send_dunning_email → Resend → NotificationLog audit
```

---

### 4.4 UX Spec Edits (`_bmad-output/ux-design-specification.md`)

#### Edit 1 — Personas (line ~35, operator)

"Internal admin. Needs override capability, full retry schedule visibility, and audit trail access" → "Internal admin. Needs audit trail access, manual status advancement for edge cases, and Django admin oversight. No retry schedule (no retries in v1)."

#### Edit 2 — UX Principles (line ~45)

**REMOVE:** "Mode clarity at all times. Supervised vs. Autopilot must be unmistakably visible. A mistaken mode assumption is a silent trust failure."

**REPLACE with:** "Per-row clarity over engine clarity. Marc decides per row, not per global setting. Each row's recommended email + status badge + amount communicates the situation at a glance."

#### Edit 3 — Mode Architecture sections (lines ~64–105)

**DELETE entire "Trial activation / Autopilot toggle" sub-section.**

**DELETE entire "Autopilot mode" sub-section.**

**DELETE entire "Supervised Mode" sub-section.**

**REPLACE with new "Daily Review Workflow" section:**
> Marc opens his SafeNet dashboard once a day (or once a week — his cadence). The dashboard shows the current month's failed payments. Each row has a recommended dunning email pre-selected based on the decline code + time since failure. Marc reviews, accepts, or overrides per row, then either clicks send-per-row or selects multiple and bulk-sends. The flow is *review, not configure.*

#### Edit 4 — Onboarding & DPA Flow (line ~92)

"The Data Processing Agreement (DPA) is a formal legal step, presented as a distinct screen before the recovery engine activates" → "...presented before the first dunning email is sent."

Update onboarding sequence (lines ~100–105):
```
1. Land on marketing site
2. Connect with Stripe (OAuth, one click)
3. Profile completion: first name, last name, company/SaaS name, password
4. Redirect to dashboard (90-day retroactive scan running in background)
5. Dashboard populates — first insight delivered
6. (When Marc is ready to send first email) DPA presented as formal step — explicit signature/acceptance
7. Email sending capability unlocked
```

**REMOVE:** "8. Autopilot / Supervised selection" + "9. Engine activates" steps.

#### Edit 5 — User flow diagrams (lines ~638–642, 695–720, 750–760)

**REMOVE entirely:** Mermaid diagram nodes "DPA accepted? → Mode selection: Autopilot or Supervised? → Engine activates / Review queue enabled" — collapse to: "DPA accepted? → Yes: Email sending unlocked / No: Stays view-only with reminder"

**REMOVE entirely:** "Journey 3: Supervised Review Queue" mermaid + narrative

**REPLACE with:** "Journey 3: Daily Failed-Payments Review" — Marc opens dashboard → sees N failed payments → reviews per row → bulk-selects 4 with similar decline codes → clicks "Send recommended (4)" → confirms in dialog → emails dispatch.

**REMOVE:** "Journey 4: Card-update detection → retry queued → retry succeeds" — entire flow gone.

**REPLACE Journey 4 with:** "Journey 4: Manual Resolve" — Marc sees a failed payment whose subscriber emailed him directly to confirm payment via wire transfer → clicks "Mark resolved" with note "Paid via wire 2026-04-28" → row clears, audit log records.

#### Edit 6 — Component inventory (line ~355)

"`BatchActionToolbar` — Supervised mode multi-select controls" → "`BatchActionToolbar` — failed-payments multi-select controls; primary action: 'Send recommended (N)'; secondary: 'Send specific (chosen type)'; tertiary: 'Mark resolved (N)' / 'Exclude (N)'."

#### Edit 7 — Sidebar / navigation (line ~556)

"mode toggle (Autopilot / Supervised)" → **REMOVE**. Sidebar simplifies.

#### Edit 8 — Anti-patterns + Empty states

Remove or reframe lines that reference "retry attempts" as anti-pattern examples. Update zero-state copy: "Nothing needs your eyes right now" → "No failed payments this month. Your subscribers are paying — keep shipping."

---

### 4.5 Sprint Status Edits (`_bmad-output/sprint-status.yaml`)

Add at top of comments block:
```
# 2026-04-29: SCOPE SIMPLIFICATION — Epic 3 v0 quarantined to archive/v0-recovery-engine
# Sprint Change Proposal: _bmad-output/sprint-change-proposal-2026-04-29.md
```

Update entries:
```yaml
  # Epic 3 (v0) — QUARANTINED 2026-04-29 to archive/v0-recovery-engine
  epic-3-v0: quarantined
  3-1-dpa-acceptance-engine-mode-selection-flow: quarantined
  3-2-autopilot-recovery-engine-rule-execution-4-state-status-machine: quarantined
  3-3-card-update-detection-immediate-retry: quarantined
  3-4-supervised-mode-pending-action-queue-batch-approval: quarantined
  3-5-subscriber-status-cards-attention-bar: quarantined

  # Epic 3 (v1) — DPA Gate, Failed-Payments Dashboard & Email Actions
  epic-3-v1: backlog
  3-1-v1-dpa-acceptance-gate: backlog
  3-2-v1-current-month-failed-payments-dashboard: backlog
  3-3-v1-per-row-send-and-manual-resolve: backlog
  3-4-v1-bulk-send-and-status-polling: backlog
  3-5-v1-recommended-email-mapping: backlog

  # Epic 4 — REVISIONS REQUIRED
  4-1-resend-integration-branded-failure-notification-email: revise-required-trigger-path
  4-2-tone-selector-settings-live-notification-preview: revise-required-expand-redirect-link-and-custom-body
  4-3-final-notice-recovery-confirmation-emails: revise-required-trigger-path

  # Epic 5 — TRIM
  5-1-subscriber-detail-panel-payment-timeline: backlog
  5-2-fraud-flag-manual-resolution: backlog
  5-3-recovery-analytics-month-over-month-dashboard: deferred-v2
  5-4-weekly-digest-email-monthly-savings-email-data-retention: backlog-split  # weekly+retention v1; monthly-savings v2

  # Epic 6 — TRIM
  6-1-operator-authentication-console-access-isolation: backlog
  6-2-scheduled-retry-dashboard-manual-override: deferred-v2
  6-3-manual-status-advancement-audit-log-viewer: backlog
```

(Story 2-2 and 2-5 don't get status changes — they're done. Their cadence-related ACs get edited in epics.md per §4.2.3 and §4.2.4 above. Code edits to honor the new cadence are tracked under a new follow-up story or treated as a small chore on main.)

---

### 4.6 Deferred Work Annotations (`_bmad-output/deferred-work.md`)

At the top of each section beginning "## Deferred from: code review of story-3-2", "story-3-3", "story-3-4", "story-3-5" and the engine-driven portions of "story-4-1" and "story-4-3", add:

```
> **MOOT under 2026-04-29 simplification — see _bmad-output/sprint-change-proposal-2026-04-29.md**
> Items below apply to the autonomous engine and are preserved on the `archive/v0-recovery-engine` branch.
> Revisit only if the v2 quarantine is reactivated.
```

Specifically these sections become moot:
- "code review of story-3-2 (2026-04-15)" — N+1 Stripe calls in `_check_subscription_cancellations`/`_detect_card_updates`, retry-burn issues, `PaymentIntent.confirm` dependency on PM attachment
- "code review of story-3-3 (2026-04-24)" — N+1 patterns in card-update/cancellation detection
- "code review of story-3-4 (2026-04-24)" — pending-action queue, batch approve, supervised-mode-specific issues
- "code review of story-3-5 (2026-04-25)" — backfill/polling-catchup duplication for engine activation
- "code review of story-4-1 (2026-04-25)" — engine-driven trigger items only; the Resend integration items themselves stay
- "code review of story-4-3 (2026-04-27)" — `is_last_retry` edge cases, FSM-trigger items; the email-shell/CTA-validation items stay

These items become non-moot if the quarantine branch reactivates. Tag with `[moot-v1, applies-v2]`.

---

## 5. Implementation Handoff

### Scope Classification: **Major**

This is a fundamental replan of an in-progress epic, with quarantine of completed code, edits across 5 planning artifacts (PRD, Architecture, UX, Epics, Sprint Status), 6 new FRs, 10 removed FRs, 8 modified FRs, and 5 new stories drafted.

### Pre-Approval Decision Gates

Before any artifact is edited or branch is created, **Sabri's input is required on the 9 open decisions in §3.5**. Most have strong recommendations; quick confirmation is sufficient.

### Handoff Plan

| Role | Responsibility |
|------|---------------|
| **PM (John)** | Apply all PRD edits per §4.1 once decisions confirmed; draft new Epic 3 v1 stories per §4.2.2; mark Epic 3 v0 as quarantined per §4.2.1 |
| **Architect (Winston)** | Apply all Architecture edits per §4.3; review and approve §3.4 PendingAction repurpose path; produce branch-creation runbook (which commits to revert on main, which to keep) |
| **UX (Sally)** | Apply all UX Spec edits per §4.4; produce updated mermaid diagrams (or coordinate with John on inline edits) |
| **SM (Bob)** | Apply Sprint Status edits per §4.5; mark deferred-work.md sections moot per §4.6; create the quarantine branch (`archive/v0-recovery-engine`) with the BRANCH_README.md per §3.2 |
| **Dev (TBA)** | Once Epic 3 v1 stories are drafted: implement 3.1-v1 → 3.5-v1 in sequence; revise Stories 4.1, 4.2, 4.3 per §4.2.5–§4.2.7; small chore on main to flip polling cadence (Story 2.2's hourly Celery beat → daily) and rip out engine-driven trigger paths from email send services |
| **TEA (QA)** | Audit existing test suite — quarantine engine tests; add coverage for new endpoints; re-evaluate the 10 pre-existing test failures captured in deferred-work 2026-04-27 (some become moot, some need fixing) |

### Success Criteria

- [ ] `archive/v0-recovery-engine` branch created with BRANCH_README.md and tagged from current `main` HEAD
- [ ] PRD edits applied; FR set diffed correctly (50 → 46 FRs); Executive Summary + journeys reflect simplified scope
- [ ] Architecture edits applied; DECLINE_RULES action vocabulary updated; quarantine map honored in code on main
- [ ] UX Spec edits applied; mode-architecture sections deleted; new daily-review workflow section added
- [ ] 5 new Epic 3 v1 stories drafted in epics.md with full ACs
- [ ] Stories 4.1, 4.2, 4.3 revised in epics.md
- [ ] Stories 2.2, 2.5 polling-cadence ACs corrected in epics.md
- [ ] Sprint status updated; deferred-work moot annotations added
- [ ] Code on main reflects: daily polling cadence, engine-driven trigger paths removed from 4.1/4.3 send services, retry tasks/payday/compliance-enforcement modules archived
- [ ] First Epic 3 v1 story (3.1-v1: DPA Gate) reaches `ready-for-dev` status

### Sequencing

1. **Today:** Sabri reviews this proposal, confirms 9 open decisions in §3.5
2. **+1 day:** John applies PRD/Epics edits; Winston applies Architecture edits; Sally applies UX edits
3. **+2 days:** Bob creates quarantine branch + BRANCH_README; updates sprint-status; annotates deferred-work
4. **+3 days:** Dev chore on main to revert engine code + flip polling cadence
5. **+4 days:** Dev begins Story 3.1-v1 (DPA Gate)
6. **+10 days:** First v1 dunning email dispatched in dev; Mid-tier client onboarding tested end-to-end
7. **+14 days:** v1 ready for first paying client

---

## 6. Approval Request

**Sabri — please confirm:**

1. **Approval to apply this proposal as written?** (yes / no / revise — if revise, specify which sections)
2. **Decisions on the 9 open items in §3.5** (most have recommended defaults; just confirm or override)
3. **Handoff sequencing** acceptable as listed in §5?

Once approved, I (John) apply PRD + Epics edits in one pass; Winston handles Architecture in parallel; Sally handles UX in parallel; Bob creates the quarantine branch and updates sprint-status. End-to-end the proposal application is ~3 days; the v1 ready-for-first-client target is ~14 days from approval.

Awaiting your call.
