---
stepsCompleted: [step-01-init, step-02-discovery, step-02b-vision, step-02c-executive-summary, step-03-success, step-04-journeys, step-05-domain, step-06-innovation, step-07-project-type, step-08-scoping, step-09-functional, step-10-nonfunctional, step-11-polish, step-12-complete]
inputDocuments:
  - brainstorming/brainstorming-session-2026-04-03-safenet.md
briefCount: 0
researchCount: 0
brainstormingCount: 1
projectDocsCount: 0
workflowType: 'prd'
classification:
  projectType: saas_b2b
  domain: fintech
  complexity: high
  projectContext: greenfield
project_name: SafeNet
---

# Product Requirements Document - SafeNet

**Author:** BMad
**Date:** 2026-04-03

## Executive Summary

SafeNet is a decline-code-aware payment recovery SaaS for solo founders and small teams (≤5 people) operating subscription businesses on Stripe. It targets the growing cohort of AI-accelerated SaaS builders who are technically capable but operationally thin — shipping fast, growing fast, and unable to invest attention in manual payment recovery.

The core problem: Stripe's native dunning is code-agnostic. It applies the same retry schedule to every failure regardless of cause — a card expiry, an insufficient funds event, and a fraud flag all receive identical treatment. SafeNet reads the decline code first, then acts. Every failed payment has a reason; SafeNet matches the fix to the reason.

**Target user:** Solo SaaS founders and teams ≤5 with existing MRR, already on Stripe, too focused on building and growing to chase failed payments manually. The pain is dual: the direct revenue loss is significant at early MRR levels, and the attention cost of manual recovery is a distraction from the highest-leverage work available to a small team.

**Primary value:** Automated, intelligent payment recovery that runs without operator involvement — freeing founders to stay focused on product and growth rather than operational fire-fighting.

**Business model:** Three-tier freemium. Free tier delivers a genuine diagnostic dashboard (90-day retroactive scan, failure landscape, estimated recoverable revenue) — no actions fire, no paywall. Mid tier activates the recovery engine: code-aware retries, tone-selector notifications, GDPR-compliant flows. Pro tier (post-MVP) adds white-label notifications, AI-assisted copy, and passive churn export. 30-day full mid-tier trial; post-trial degradation to reduced polling frequency rather than hard paywall.

### What Makes This Special

**Diagnosis before action.** Competitors (Churnbuster, Gravy, Paddle Retain) compete on retry schedules. SafeNet competes on diagnostic accuracy. The decline-code rule engine maps 30+ Stripe codes to distinct recovery trees — `card_expired` never retries, it triggers a card-update notification immediately; `insufficient_funds` waits for payday timing; fraud flags stop all actions and surface for manual review.

**Compliance as brand pillar, not feature.** EU-aware retry blocking (SEPA/UK direct debit re-authorization rules) and GDPR-compliant notification flows are built into v1 — not bolted on later. This is an explicit differentiator for European SaaS founders underserved by US-centric tools.

**The free tier sells itself.** The diagnostic dashboard's "estimated recoverable revenue" number is always visible and always larger than the monthly fee. The free tier is a permanent, live ROI calculator — not a crippled preview.

**Constrained action set as trust signal.** SafeNet does exactly two things: retry the original payment amount, or notify the end customer. No partial charges, no silent plan downgrades. Simplicity as an explicit trust mechanism.

## Project Classification

- **Project Type:** B2B SaaS — web dashboard + backend recovery engine, subscription tiers, Stripe integration
- **Domain:** Fintech — payment processing, compliance (GDPR, EU retry rules), financial data handling
- **Complexity:** High — regulatory surface area, Stripe authorization model, fraud handling, audit requirements, SOC 2 planned post-MVP
- **Project Context:** Greenfield

## Success Criteria

### User Success

- **First-login revelation:** Within 5 minutes of Stripe Connect authorization, the user sees a complete 90-day retroactive failure landscape — total failed payments, estimated recoverable revenue by decline code, and failure distribution. The dashboard is never empty on first load.
- **30-day proof cycle:** The primary conversion trigger is not the dashboard — it is the first month of the recovery engine running. After 30 days, the user has a concrete record: failures detected, retries fired, payments recovered, revenue protected. The "aha moment" is proof, not promise.
- **Zero operational involvement:** A successfully onboarded Mid-tier user runs SafeNet entirely on autopilot. No manual actions required after initial setup. Recovery happens without the founder's attention.
- **Trusted brand voice:** Notifications sent to end-customers reflect the client's chosen tone (Professional / Friendly / Minimal) and never feel like third-party spam. End-customers engage with the notification as they would with the SaaS brand itself.

### Business Success

| Horizon | Target |
|---------|--------|
| Week 10 | First paying Mid-tier client (First MRR) |
| Month 3 | 5 paying Mid-tier clients (≥€100 MRR), 10 active free-tier clients |
| Month 12 | 30+ paying clients, positive net revenue after infrastructure costs, Pro tier launched with at least 5 clients |

- Free-to-paid conversion rate target: ≥30% of free-tier users who complete the 30-day trial upgrade to Mid.
- The "estimated recoverable revenue" figure shown on the free dashboard must always visibly exceed the monthly Mid-tier fee — this is a permanent product constraint, not just a launch condition.

### Technical Success

- **Zero security incidents.** This is the non-negotiable 2am hotfix threshold. No unauthorized access to client Stripe tokens, no exposure of end-customer payment metadata, no data leaks of any kind. Security is the only absolute failure condition.
- **100% scheduled retry execution.** Every retry queued by the rule engine fires within its scheduled window. Missed retries are a direct revenue failure for clients and a trust failure for SafeNet.
- **Polling reliability ≥99.9% uptime.** The hourly polling job is the heartbeat of the system. Silent failures are unacceptable — missed polling cycles must be detected, alerted, and logged.
- **Rule engine correctness.** Zero false-positive fraud flags (marking a legitimate failure as fraud stops all recovery actions permanently). Fraud classification must be conservative and auditable.

### Measurable Outcomes

- Time-to-first-insight ≤5 minutes post Stripe Connect authorization
- First-login dashboard populated with retroactive data before user leaves the onboarding flow
- Free-tier trial conversion ≥30% (30-day trial → Mid upgrade)
- Recovery rate for `insufficient_funds` failures: target ≥40% of payday-aware retries succeed
- Zero client-reported false fraud flags at MVP launch
- All GDPR and geo-aware compliance requirements verified before first paying client onboards

## Product Scope

### MVP — Minimum Viable Product (Weeks 1–10)

**Engine:**
- Stripe Express Connect OAuth onboarding (zero API key handling)
- Hourly polling-based failure detection (replaces webhook dependency)
- 30+ decline-code rule engine with distinct recovery trees per code
- Four-status state machine: Active → Recovered / Passive Churn / Fraud Flagged
- Bounded retry with code-dependent caps
- Payday-aware retry calendar for `insufficient_funds`
- Geo-aware compliance layer: EU/UK retry blocking → routes to notify-only
- Supervised mode / Autopilot toggle
- Internal admin override panel (operator-facing, not client-facing)

**Dashboard (Free + Mid):**
- 90-day retroactive scanner + first-login populated state
- Four-status customer view (people-first, not transaction-first)
- Estimated recoverable revenue KPI (permanent free-tier feature)
- Monthly comparison view (MoM trends)
- Recovery analytics section
- Optional weekly digest email (opt-in, disabled by default) + triggered onboarding email
- Single anchored CTA on "estimated recoverable revenue"

**Notifications (Mid):**
- One crafted default template per notification type
- Tone selector: 3 presets (Professional / Friendly / Minimal)
- GDPR-compliant flow: opt-out links, data processor agreements, sender identification
- Graceful final notice (last-attempt email, explicit and honest)
- Recovery confirmation email to end-customer on successful retry

**Business mechanics:**
- 30-day full Mid-tier trial
- Post-trial degraded free tier (polling drops from hourly to twice-monthly; delay visible in dashboard)
- "SafeNet saved you €X" monthly email on billing date
- Single-owner account (no team roles)
- Free + Mid tiers at launch; Pro announced as "coming soon"

**Compliance (required before first paying client):**
- GDPR: data processor agreements, opt-out in every notification, transparent sender identification, data retention policy
- Geo-aware retry blocking: EU SEPA and UK direct debit contexts route to notify-only (no retry without re-authorization)
- Least-privilege data model: SafeNet stores only Stripe event metadata (payment intent IDs, decline codes, timestamps, retry outcomes) — zero raw card data
- Transparent data handling documentation published at launch

### Growth Features (Post-MVP)

| Feature | Trigger |
|---------|---------|
| Pro tier: white-label notifications | After first 20 Mid clients |
| Pro tier: AI-assisted notification copy | After first 20 Mid clients |
| Pro tier: passive churn CSV export (Mailchimp/Klaviyo/Brevo-ready) | After first 20 Mid clients |
| Proactive card expiry detection (30-day advance alert) | Pro tier launch |
| Role-based team access | Dedicated workstream, post-MVP |
| Shareable payment health report (branded export) | Post-traction |
| SOC 2 Type I planning and execution | Post-MVP (architecture decisions made now) |
| Stripe App Marketplace listing | Validate economics first |

### Vision (Future)

- PSP-agnostic expansion: Paddle, Braintree, Adyen — same rule engine, new adapters
- Anonymized industry benchmarks: "SaaS companies similar to yours recover 58% of these cases; you're at 71%"
- Mid-market segment (teams >5, different sales motion)
- Custom retry timeframe configurations per client
- SEO content engine targeting failed payment / dunning search intent

## User Journeys

### Journey 1: The Founder — Onboarding & The 30-Day Proof (Happy Path)

**Persona:** Marc, 34. Solo founder. Built a B2B productivity tool with AI coding assistants over 4 months, now at €2,800 MRR. He checks Stripe every Monday morning — a habit born from anxiety, not process. One Monday he notices his gross revenue and net deposits keep diverging. He knows failed payments exist. He doesn't know how many, which kind, or how much he's losing. He's too deep in a feature sprint to investigate manually.

**Opening Scene:** Marc finds SafeNet via a thread on Indie Hackers titled "how I recovered €400 in a week without touching my code." He's skeptical — another retry tool. He reads the landing page. The line "Stripe doesn't read the decline code. We do." stops him.

**Rising Action:** He clicks Connect with Stripe. OAuth flow, one click, no API key. He's redirected to the dashboard. A scan animation runs for 8 seconds. Then the screen populates: 23 failed payments in 90 days. €640 estimated recoverable. Breakdown by decline code — 11 `insufficient_funds`, 7 `card_expired`, 3 `do_not_honor`, 2 `fraudulent`. He didn't know `card_expired` never retries itself. He didn't know what `do_not_honor` meant. He does now. The CTA reads: "Activate recovery engine — €29/month." The math is immediate.

He starts the 30-day trial. Switches to Autopilot. Closes the tab.

**Climax:** Day 18. Marc gets an email from SafeNet: "Payment recovered — €89 from a subscriber who updated their card." He hadn't thought about it once since setup. The engine caught an `insufficient_funds` case, waited for the 1st of the month payday window, retried, and succeeded. The subscriber got a friendly confirmation email. No support ticket. No churn.

Day 30. Marc's billing date arrives. An email lands: *"This month, SafeNet recovered €310 for you. Your plan costs €29. Net benefit: €281."* He upgrades to Mid before the trial expires.

**Resolution:** Marc's dashboard is now a weekly ritual, not anxiety. Every Monday he sees the recovery analytics section — who's in Active status, who recovered, who graduated to Passive Churn. He knows exactly what's happening in his payment infrastructure. SafeNet runs without him.

*This journey reveals requirements for: Stripe Connect OAuth, retroactive scanner, dashboard KPIs, trial mechanics, autopilot mode, payday-aware retry, recovery confirmation email, "SafeNet saved you" billing email, upgrade flow.*

---

### Journey 2: The Founder — The Fraud Flag (Edge Case)

**Persona:** Same Marc, three weeks into his trial. 47 active subscribers.

**Opening Scene:** Marc logs in to check his dashboard. One subscriber — a €120/month client, one of his best — has a red badge: **Fraud Flagged**. No retry queued. No notification sent. Just a flag and a note: *"Decline code: fraudulent. All actions stopped. Manual review recommended."*

**Rising Action:** Marc's first reaction is alarm. His second is confusion — this customer paid reliably for 6 months. He clicks through to the customer detail. SafeNet shows him the exact Stripe event: `charge.failed`, decline_code: `fraudulent`, timestamp. The customer's history: 6 successful payments, then this. SafeNet did nothing — no retry, no email to the customer. Just surfaced the signal cleanly.

Marc reaches out to the customer directly via email, outside SafeNet's scope. The customer replies within the hour: their card issuer had flagged their card after an unrelated compromise. They've already issued a new card. They send the new card details. Marc marks the case as resolved in SafeNet and logs the recovery manually.

**Climax:** Marc realizes what didn't happen: SafeNet didn't retry a fraud-flagged card (which would have triggered additional fraud alerts with the issuer), didn't send an automated email to a confused customer who was already dealing with a security incident, didn't silently drop the subscriber.

**Resolution:** Marc trusts the rule engine more after this edge case than after the happy path. He adds a note to his internal Notion: *"SafeNet is conservative. That's the feature."*

*This journey reveals requirements for: fraud flag status, full action stop on fraud code, clear dashboard surfacing, customer history view, audit trail, manual resolution flow.*

---

### Journey 3: The End-Customer — The Failed Payment They Almost Ignored

**Persona:** Sophie, 28. UX designer. Pays €39/month for Marc's productivity tool. She doesn't think about SaaS billing unless something breaks.

**Opening Scene:** Sophie gets an email. Subject: *"Quick heads up about your payment."* It's in the same visual tone as the app she uses — clean, minimal, direct. Sender is Marc's brand, not some third-party dunning service. She almost misses it in her inbox but the subject line is understated enough to read as human.

**Rising Action:** The email explains her payment didn't go through this month — her card expired. It doesn't lecture her. It doesn't threaten account suspension in bold red text. It gives her a single link to update her payment method on Marc's Stripe portal. It says clearly: *"Your access continues while you update your details."* At the bottom, a small one-liner: *"This is an automated message. You can opt out of payment notifications here."* GDPR link included.

Sophie clicks the link, updates her card in 90 seconds, and goes back to what she was doing.

**Climax:** The next hourly poll picks up the card update. SafeNet queues an immediate retry. It succeeds. Sophie gets a second email: *"All sorted — payment confirmed. Thanks for updating your details."* She barely registers it. Her subscription continues.

**Resolution:** Sophie never felt chased. She never felt surveilled. The experience was indistinguishable from a well-run SaaS handling billing in-house.

*This journey reveals requirements for: branded notification email, card-update CTA, clear opt-out link, data processor agreement footer, GDPR compliance, recovery confirmation email, retry on card update detection.*

---

### Journey 4: The SafeNet Operator — The Midnight Override

**Persona:** The SafeNet operator. It's 11pm. Checking the admin override panel during the first week of live clients.

**Opening Scene:** Internal admin view open. Three retries scheduled to fire before 6am. Two look clean — `insufficient_funds` cases, payday timing confirmed, notification history normal. The third catches attention: an `authorization_failure` that's been retried twice already, scheduled for a third attempt at 4am. The client's retry cap for this code is set to 3. The pattern feels off — the customer has been in Active status for 19 days, never responded to two notifications, and the card issuer has declined both previous retries with the same code.

**Rising Action:** Pulling up the Stripe event log for this payment intent. The decline isn't changing — same issuer, same code, same outcome. A third retry at 4am will just add noise and potentially irritate the card issuer.

**Climax:** Override the retry from the admin panel. Add a note to the event log: *"Manual override — pattern suggests card blocked at issuer level, not temporary. Escalated to Passive Churn early."* Advance the customer's status to Passive Churn manually. The 4am retry is cancelled.

**Resolution:** No retry fires. The client's dashboard shows the customer correctly graduated to Passive Churn with a full audit trail. In the morning, a new heuristic is added to the engine: flag `authorization_failure` cases with 2+ identical-code retries for human review rather than automatic third retry.

*This journey reveals requirements for: internal admin override panel, retry schedule visibility, manual status advancement, event log with notes, audit trail, admin-only access controls.*

---

### Journey Requirements Summary

| Capability Area | Revealed By |
|----------------|-------------|
| Stripe Connect OAuth + retroactive scanner | Journey 1 |
| Decline-code dashboard with failure breakdown | Journey 1 |
| Autopilot / Supervised mode toggle | Journey 1 |
| Payday-aware retry execution | Journey 1 |
| Trial mechanics + upgrade flow | Journey 1 |
| "SafeNet saved you" billing email | Journey 1 |
| Fraud flag status + full action stop | Journey 2 |
| Customer detail view + payment history | Journey 2 |
| Manual resolution flow + audit trail | Journey 2, 4 |
| Branded notification email with tone selector | Journey 3 |
| Card-update CTA + GDPR opt-out | Journey 3 |
| Recovery confirmation email | Journey 3 |
| Internal admin override panel | Journey 4 |
| Retry schedule visibility for operator | Journey 4 |
| Manual status advancement | Journey 4 |
| Admin-only access controls | Journey 4 |

## Domain-Specific Requirements

### Compliance & Regulatory

- **PCI DSS scope:** SafeNet is explicitly out of PCI DSS scope. No cardholder data (card numbers, CVVs, expiry dates) is stored, processed, or transmitted. All card operations execute through Stripe's API exclusively. SafeNet stores only Stripe event metadata: payment intent IDs, decline codes, timestamps, and retry outcomes.
- **GDPR (EU):** All notifications are classified as transactional messages under contractual necessity — no marketing content permitted in any notification template. Every notification includes a compliant opt-out link and clear sender identification. A Data Processing Agreement (DPA) must be signed by each client before the recovery engine is activated — this is a hard gate, not a soft recommendation.
- **CAN-SPAM (US) / CASL (Canada):** All notifications qualify as transactional messages (tied to existing subscription relationship, zero commercial content). No additional consent mechanism required beyond GDPR opt-out already implemented. Jurisdictional coverage achieved through transactional classification.
- **EU/UK payment retry rules:** SEPA direct debit and UK direct debit contexts legally require cardholder re-authorization before retry. SafeNet's geo-aware layer detects these contexts and routes to notify-only, blocking all automated retries. This is a non-overridable engine rule.

### Technical Constraints

- **Stripe OAuth token security:** Tokens encrypted at rest using AES-256 in the database. Encryption key stored exclusively in Railway encrypted environment secrets — never in the database. A database breach alone is insufficient to decrypt tokens; both DB access and environment secret access are required simultaneously.
- **Minimal data footprint:** SafeNet stores the minimum viable dataset. No end-customer personally identifiable information beyond email address (required for notifications). No payment method details. No account balances. Data retention policy: event metadata retained for 24 months, then purged.
- **Audit trail:** Every engine action (retry fired, retry cancelled, notification sent, status change, manual override) is logged with timestamp, actor (engine or operator), and outcome. Audit logs are append-only and cannot be modified or deleted through the application layer.
- **Least-privilege access:** SafeNet requests read-only Stripe access where possible. Write access (retry execution) scoped exclusively to the specific payment intent in question. No broad account-level write permissions.

### Integration Requirements

- **Stripe Express Connect (MVP):** OAuth-based authorization. Stripe handles KYC/AML for connected accounts. SafeNet inherits no KYC/AML obligations at MVP stage.
- **Email delivery provider:** Transactional email only (e.g. Resend, Postmark). No marketing email platform. Mid-tier sends from SafeNet-managed shared domain; Pro-tier sends from client's custom domain. Provider must support both shared and custom sending domains, DKIM/SPF authentication, and bounce handling.
- **Data Processing Agreement (DPA):** Required from every client before engine activation. DPA documents: what data SafeNet processes, on whose behalf, for what purpose, with what retention policy, and under what security measures.

### Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Retry fires causing end-customer overdraft | Supervised mode available — client explicitly authorizes each retry before firing. In Autopilot, retry timing rules (payday-aware, fixed delays) are designed to minimize insufficient-funds scenarios. |
| False fraud flag stops legitimate recovery permanently | Fraud classification is conservative and auditable. Client can manually resolve and log any fraud flag. No automated re-classification. |
| Stripe token compromise | AES-256 DB encryption + env-level key storage. Tokens scoped to minimum required permissions. |
| Notification sent to opted-out end-customer | Opt-out state stored per end-customer per client. Engine checks opt-out status before every notification action. |
| GDPR breach via email provider | DPA required with email provider. End-customer email addresses not stored beyond active recovery window. |
| Retry cap exceeded without client awareness | Dashboard surfaces Passive Churn status prominently. Weekly digest email includes new Passive Churn count. |

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Diagnosis-First Dunning**
SafeNet reframes the dunning problem from "when to retry" to "why did it fail, and what does that specific reason require?" The decline-code rule engine maps 30+ Stripe failure codes to distinct recovery trees — a structural innovation in how payment recovery is approached. `card_expired` never retries (it's pointless); `insufficient_funds` waits for payday timing; `fraudulent` stops all automation immediately. No competitor applies this logic. This is SafeNet's primary moat.

**2. Payday-Aware Retry Calendar**
Payday timing has been used in consumer lending and debt collection for decades. SafeNet applies it to B2B SaaS subscription recovery for the first time. For `insufficient_funds` failures, retries fire within a 24-hour window after the 1st or 15th of the month — the two most common payday dates globally. Simple, explainable, concretely differentiated on the landing page.

**3. Compliance as Architecture, Not Feature**
EU SEPA and UK direct debit retry restrictions are non-overridable engine rules — not a settings toggle that can be misconfigured. GDPR-compliant notification flows and DPA requirements are hard gates before engine activation. SafeNet is the first dunning tool designed from the ground up for global SaaS, not US-first SaaS. This creates a defensible first-mover position with European solo founders who are systematically underserved by existing tools.

### Market Context & Competitive Landscape

| Competitor | Approach | SafeNet Gap |
|------------|----------|-------------|
| Churnbuster | Stripe-native retry schedules | Code-agnostic, US-centric |
| Gravy | Human-assisted recovery (high-touch, mid-market) | Not self-serve, not solo-founder-targeted |
| Paddle Retain | Paddle-platform-only | Not Stripe-native |
| Stripe native dunning | Basic retry cadence | No decline-code intelligence, no compliance layer |

No existing tool combines: (1) decline-code-aware rule engine + (2) GDPR/EU compliance built-in + (3) solo-founder self-serve + (4) transparent freemium with live ROI signal.

### Validation Approach

- **Diagnosis-first:** Validated when first free-tier users see their 90-day retroactive breakdown and recognize the failure taxonomy without explanation. Qualitative signal: "I didn't know `card_expired` retrying was useless until I saw this."
- **Payday-aware retry:** Validated by measuring `insufficient_funds` recovery rate at payday-window retries vs. fixed-delay retries. Target: ≥40% recovery rate at payday window.
- **Compliance moat:** Validated when first EU-based client explicitly cites GDPR/geo-compliance as the reason they chose SafeNet over alternatives.

### Risk Mitigation

| Innovation Risk | Mitigation |
|----------------|-----------|
| Stripe ships native decline-code intelligence | SafeNet's compliance depth (EU rules, DPA gates, GDPR flows) is harder to replicate than retry logic. Compliance moat > algorithm moat. |
| Payday timing doesn't improve recovery rate meaningfully | A/B testable within the engine. If data shows no improvement, fall back to fixed-delay with no architectural change. |
| Market too small (not enough solo SaaS founders) | AI coding tools are accelerating cohort growth. Timing bet — not a structural market constraint. |

## B2B SaaS Specific Requirements

### Project-Type Overview

SafeNet is a single-tenant B2B SaaS at MVP. Each client account maps to one Stripe Connect authorization and one owner user. The architecture is deliberately simple at launch — optimized for speed of build and reliability, not organizational complexity. The data model is designed to expand to multi-user accounts without structural migration.

### Technical Architecture Considerations

**Tenant Model:**
- V1: One `Account` record per Stripe Connect authorization. One `User` FK per `Account` (owner). No shared access, no invite system.
- Data model anticipates future expansion: `Account` ↔ `Membership` ↔ `User` join table will be addable post-MVP without schema migration on the `Account` or `User` tables.
- All data queries are scoped to `account_id` from day one — no global queries permitted. This ensures tenant isolation is enforced architecturally, not just by convention.

**Permission Model (RBAC):**
- V1: Single role — `owner`. Full access to all account data and settings.
- No granular permissions at MVP. No invite flow, no viewer roles, no read-only access.
- Future roles anticipated (post-MVP): `owner`, `member` (engine management), `viewer` (dashboard read-only). Architecture supports this via the membership table expansion without touching core engine logic.

### Subscription Tiers

| Tier | Price | Features | Status |
|------|-------|----------|--------|
| Free | €0/month | Dashboard + 90-day retroactive scan + failure landscape KPIs. Polling: hourly during 30-day trial, drops to twice-monthly post-trial. No recovery engine. Single CTA anchored to "estimated recoverable revenue". | Launch |
| Mid | €29/month | Full recovery engine: decline-code rules, payday-aware retries, geo-compliance layer, Supervised/Autopilot toggle, tone-selector notifications (3 presets), GDPR-compliant flows, recovery analytics, weekly digest email, "SafeNet saved you" billing email. Emails sent from SafeNet-managed domain (`payments.safenet.app`) with client brand name in From field. No DNS setup required. | Launch |
| Pro | €79/month | Mid tier + white-label notifications with full custom sending domain (client's own domain — `billing@client-app.io`), zero SafeNet footprint in email headers, AI-assisted notification copy, passive churn CSV export (Mailchimp/Klaviyo/Brevo-ready), proactive card expiry detection. SafeNet provides DNS configuration guide (DKIM/SPF/DMARC). | Announced at launch, built after first 20 Mid clients |

**Trial mechanics:** 30-day full Mid-tier access for all new accounts. No credit card required to start trial. On day 30, non-upgraders are automatically downgraded to Free (degraded polling). Degradation is visible in the dashboard ("your next scan is in X days").

**Billing:** Stripe Billing for SafeNet's own subscription management. Consistent with the product's Stripe-native positioning.

### Integration List

**MVP integrations (required at launch):**

| Integration | Purpose | Notes |
|-------------|---------|-------|
| Stripe Express Connect | Client Stripe account authorization, payment data read, retry execution | OAuth flow, no API key handling by client |
| Transactional email provider (Resend or Postmark) | End-customer notifications + client digest emails | Two-mode architecture: Mid tier uses SafeNet-managed shared sending domain (`payments.safenet.app`) — no client DNS setup. Pro tier uses client's custom domain — full DKIM/SPF/DMARC, SafeNet provides setup guide. Per-email cost identical across both modes. |
| Stripe Billing | SafeNet's own subscription and trial management | Dogfooding the Stripe ecosystem |

**Post-MVP integrations (deferred):**

| Integration | Trigger |
|-------------|---------|
| REST API / webhook export | If MVP clients request programmatic access — Python backend makes this straightforward to add |
| Zapier / Make connector | Post-traction, if workflow automation demand surfaces |
| Stripe Standard Connect | Phase 2 — unlocks broader Stripe Marketplace eligibility |
| Paddle, Braintree, Adyen | PSP-agnostic Phase 2 — same rule engine, new adapters |

### Implementation Considerations

- **Backend:** Python + Django. Django admin panel serves as the internal operator tool (override panel, audit log viewer) at MVP — no custom admin UI needed.
- **Scheduler:** Celery + Redis for the hourly polling job and retry execution. Fully locally testable against Stripe test mode.
- **Database:** PostgreSQL. All financial event metadata stored with ACID compliance. Tenant isolation enforced at query level via `account_id` scoping.
- **Frontend:** Next.js. Dashboard is the primary client interface. No mobile-first requirement — target users are on desktop when reviewing payment health.
- **Local dev:** Docker Compose. One command spins up Django + Celery + Redis + PostgreSQL + Stripe CLI webhook listener. Identical to production environment.
- **Production:** Railway. No DevOps expertise required. Encrypted environment secrets for Stripe token encryption keys.
- **Testing:** pytest + Stripe test mode. All engine logic tested locally before any production deploy. Three-layer quality gate: AI coding tools generate → local test suite passes → peer code review before merge.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Revenue MVP — the smallest deployable product that generates first MRR and validates the core assumption: that decline-code-aware recovery outperforms generic scheduled retry. The free tier validates the diagnostic value proposition; the Mid tier validates willingness to pay for automated recovery. Both must work end-to-end before launch.

**Build model:** Solo builder + AI coding tools + local test suite + peer code review. Every feature must be buildable, testable locally against Stripe test mode, and reviewable before production deploy. Complexity that breaks this model gets deferred.

**Resource requirements:** One technical founder. 10-week build window. Railway for zero-DevOps production. Django admin as the internal operations panel — no custom admin UI in scope.

### MVP Feature Set (Phase 1 — Weeks 1–10)

**Core user journeys fully supported:**
- Journey 1: Founder onboarding → 90-day scan → 30-day proof cycle → upgrade
- Journey 2: Fraud flag detection → safe stop → manual resolution
- Journey 3: End-customer notification → card update → recovery confirmation
- Journey 4: Operator override panel → manual retry cancellation → audit trail

**Must-have capabilities (nothing ships without these):**

| Capability | Why it's non-negotiable |
|-----------|------------------------|
| Stripe Express Connect OAuth | Without this, no product exists |
| 90-day retroactive scanner | Empty first-login kills free tier conversion |
| Decline-code rule engine (30+ codes) | Core differentiator — removes it and SafeNet is just another retry tool |
| Four-status state machine | Operational integrity — SafeNet must know the state of every customer |
| Payday-aware retry calendar | Primary `insufficient_funds` differentiator |
| Geo-aware compliance layer | Non-negotiable for EU clients — legal requirement |
| GDPR notification flows + DPA gate | Hard compliance requirement before first paying client |
| Supervised / Autopilot toggle | Liability and trust — clients must explicitly own their retry authorization model |
| AES-256 token encryption + env-key storage | Security non-negotiable — see 2am hotfix threshold |
| Free + Mid tier + 30-day trial + degraded fallback | Business model requires both tiers to work at launch |
| Internal admin override panel | Operational safety net during early operation |

### Post-MVP Features

See **Product Scope → Growth Features** and **Vision** sections for the full phased feature roadmap. Phase 2 triggers after first 20 Mid clients; Phase 3 is post-traction expansion.

### Risk Mitigation Strategy

**Technical risks:**

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Rule engine misclassifies a decline code | High | Conservative defaults — unknown codes route to fixed-delay retry + notify, never fraud flag. Fraud flag requires exact code match only. |
| Celery polling job silently fails | High | Dead-letter queue + alerting on missed polling cycles. Operator email alert if no poll in 90 minutes. |
| Stripe API rate limits hit during retroactive scan | Medium | 90-day scan runs as a background job with exponential backoff. Never blocks the UI. |
| Railway downtime during scheduled retry window | Medium | Celery retries with jitter on infrastructure failure. Missed retry flagged in audit log. |

**Market risks:**

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Stripe ships native decline-code intelligence | Medium | Compliance moat (EU rules, DPA gates) is harder to replicate than algorithm. Community brand via build-in-public creates switching cost. |
| Target market too small at launch | Low | AI coding tools are minting new solo SaaS founders at accelerating rate. Timing is structural advantage. |
| Free tier users never convert | Medium | 30-day trial gives Mid-tier access by default. Conversion trigger is demonstrated recovery, not dashboard alone. Degraded free tier creates honest urgency. |

**Resource risks:**

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Build takes longer than 10 weeks | Medium | Concierge onboarding for first 10 clients — manual where needed. Self-serve infrastructure can follow proven manual workflows. |
| Solo founder burnout / context switching | Medium | Week 9 community outreach only begins after local build is complete and tested. No GTM work before the product is ready. |
| Support overhead from early clients | Low | Django admin panel handles all operator interventions. Concierge onboarding provides direct channel to catch issues before they become tickets. |

## GTM & Launch Approach

**Channel:** Community-led. Primary channels at launch: Indie Hackers, r/SaaS, build-in-public posts. No paid acquisition at MVP stage. Inbound intent from these communities converts faster than cold outreach for a solo founder with no existing network.

**Concierge onboarding (Weeks 9–10):** The first 10 clients are onboarded manually — operator connects their Stripe, walks through the dashboard, explains the rule engine in a 1:1 session. Self-serve onboarding is built after doing it manually 10 times. Manual first → automate what you understand.

**GTM sequence:**
1. Weeks 1–8: Build and test locally. Zero GTM activity.
2. Week 9: Community posts go live. First 3 free-tier users onboarded concierge-style.
3. Week 10: First upgrade conversation from users who have seen the 30-day proof.
4. Month 3 target: 5 paying Mid-tier clients, 10 active free-tier clients.

**Pricing anchoring:** The free dashboard's "estimated recoverable revenue" figure is always visible and always exceeds the €29/month Mid fee. This is not just a UX principle — it is a permanent product constraint. The free tier does the sales job inside the product.

## Functional Requirements

### Account & Onboarding

- **FR1:** A new user can connect their Stripe account to SafeNet via OAuth without handling API keys
- **FR2:** SafeNet can perform a retroactive 90-day payment failure scan immediately after Stripe Connect authorization
- **FR3:** A client must acknowledge and sign a Data Processing Agreement before the recovery engine is activated
- **FR4:** A client can choose between Supervised mode and Autopilot mode as their retry authorization model
- **FR5:** A client can switch between Supervised and Autopilot mode at any time after initial setup
- **FR48:** Each client account supports exactly one user at MVP — multi-user access and team invitations are not available

### Payment Failure Detection

- **FR6:** SafeNet can detect new failed payment events from a connected Stripe account on an hourly polling cycle
- **FR7:** SafeNet can classify each failed payment by its Stripe decline code
- **FR8:** SafeNet can display a breakdown of all detected failures by decline code category
- **FR9:** SafeNet can calculate and display an estimated recoverable revenue figure based on detected failures

### Recovery Engine

- **FR10:** SafeNet can apply distinct recovery rules to each decline code category (retry-only, notify-only, retry+notify, no-action)
- **FR11:** SafeNet can schedule `insufficient_funds` retries within a 24-hour window after the 1st or 15th of the month
- **FR12:** SafeNet can enforce a maximum retry count per failure by decline code category: `insufficient_funds` (3 retries), `do_not_honor` / `generic_decline` (2 retries), `card_velocity_exceeded` (1 retry), `card_expired` (0 retries — notify only), all other codes (1 retry unless overridden by rule engine)
- **FR13:** SafeNet can detect EU/UK payment contexts (identified via Stripe payment method country or customer billing address country) and route them to notify-only, blocking automated retries
- **FR47:** SafeNet can detect when an end-customer updates their payment method and queue an immediate retry for their most recent Active-status failure, independent of the payday-aware schedule
- **FR14:** In Supervised mode, SafeNet queues pending actions for explicit client approval before execution
- **FR15:** In Autopilot mode, SafeNet executes recovery actions automatically per the rule engine without client intervention

### Customer Status Management

- **FR16:** SafeNet assigns and displays one of four statuses to each end-customer with a failed payment: Active, Recovered, Passive Churn, Fraud Flagged
- **FR17:** SafeNet can transition a customer from Active to Recovered when a retry succeeds
- **FR18:** SafeNet can transition a customer to Passive Churn when the retry cap is exhausted without recovery
- **FR19:** SafeNet immediately flags a customer as Fraud Flagged and stops all actions when a fraud decline code is detected
- **FR20:** A client can view the payment history and current status for any individual end-customer
- **FR21:** A client can manually resolve a Fraud Flagged status and record a resolution reason
- **FR46:** SafeNet can detect when an end-customer's Stripe subscription moves to a non-recoverable state (`cancelled`, `unpaid`, `paused`) or is flagged as `cancel_at_period_end`, and automatically stops all recovery actions, graduating the customer to Passive Churn with the specific reason recorded

### Notifications

- **FR22:** SafeNet can send a branded email notification to an end-customer when their payment fails
- **FR23:** A client can select the notification tone from three presets (Professional / Friendly / Minimal)
- **FR24:** SafeNet can send a final notice email to an end-customer on the last retry attempt, before graduating them to Passive Churn
- **FR25:** SafeNet can send a payment recovery confirmation email to an end-customer when a retry succeeds
- **FR26:** Every notification sent to an end-customer includes a functional opt-out mechanism
- **FR27:** SafeNet suppresses all future notifications for an end-customer who has opted out via a SafeNet notification link. All SafeNet notifications are classified as transactional messages (contractual necessity) — a standard marketing opt-out from the client's own communications does not suppress SafeNet notifications.
- **FR28:** Mid-tier clients' notifications are sent from a SafeNet-managed shared sending domain with the client's brand name in the From field

### Dashboard & Analytics

- **FR29:** A client's dashboard is populated with retroactive scan data on first login — no empty state
- **FR30:** A client can view failures segmented by decline code, customer status, and estimated recoverable revenue
- **FR31:** A client can view recovery analytics showing recovered payments, successful retry attempts, and notifications that drove card updates
- **FR32:** A client can view a month-over-month comparison of failure rate, recovery rate, revenue protected, and Passive Churn count
- **FR33:** A client can opt in to receive a weekly digest email summarizing recovery activity, active retries, and new Passive Churn flags — disabled by default, togglable from account settings
- **FR34:** SafeNet sends a triggered onboarding email to the client when their first scan completes

### Subscription & Billing

- **FR35:** SafeNet provides full Mid-tier access to any new account for 30 days without requiring a payment method
- **FR36:** SafeNet downgrades a non-converting account to the Free tier after the 30-day trial, reducing polling to twice-monthly
- **FR37:** A Free-tier client can see the time remaining until their next payment scan in the dashboard
- **FR38:** SafeNet sends a monthly email to active Mid-tier clients showing recovered revenue versus subscription cost
- **FR39:** A client can upgrade from Free to Mid tier from a single CTA anchored to the estimated recoverable revenue figure

### Operator Administration

- **FR40:** The SafeNet operator can view all scheduled retries across all accounts before they fire
- **FR41:** The SafeNet operator can cancel a scheduled retry and record a reason in the audit log
- **FR42:** The SafeNet operator can manually advance a customer's status and record the reason
- **FR43:** SafeNet records every engine action in an append-only audit log with timestamp, actor, and outcome
- **FR44:** The SafeNet operator can view the full audit log for any customer or account
- **FR45:** The operator console is accessible only to authenticated SafeNet operators and is not exposed to clients

## Non-Functional Requirements

### Security

- **NFR-S1:** All Stripe OAuth tokens are encrypted at rest using AES-256; the encryption key is stored exclusively in environment secrets and never in the database
- **NFR-S2:** All data in transit is encrypted using TLS 1.2 minimum
- **NFR-S3:** SafeNet stores zero raw cardholder data — only Stripe event metadata (payment intent IDs, decline codes, timestamps, retry outcomes)
- **NFR-S4:** All operator console access requires authentication; the console is not accessible to client accounts
- **NFR-S5:** All data queries are scoped by tenant identifier at the application layer — no cross-tenant data access is possible through the application
- **NFR-S6:** Any confirmed security incident triggers a production hotfix within 4 hours of confirmation — no exceptions, no scheduled release queue

### Reliability

- **NFR-R1:** The hourly polling job executes every 60 minutes (±5 minutes tolerance); a missed cycle triggers an operator alert within 90 minutes
- **NFR-R2:** Scheduled retries fire within their designated time window with ≤15 minutes variance
- **NFR-R3:** Every engine action either succeeds or is logged as failed with a reason — zero silent failures permitted
- **NFR-R4:** System uptime target: ≥99.5% measured monthly
- **NFR-R5:** The job queue implements dead-letter handling — failed jobs are captured, logged, and surfaced for operator review rather than silently dropped

### Performance

- **NFR-P1:** Dashboard loads within 3 seconds for accounts with up to 500 end-customers
- **NFR-P2:** The 90-day retroactive scan runs as a background job and does not block the dashboard UI at any point
- **NFR-P3:** First scan data is visible in the dashboard within 5 minutes of Stripe Connect authorization
- **NFR-P4:** Polling retries automatically on rate limit errors without hard failure — no polling cycle is abandoned due to temporary API throttling

### Scalability

- **NFR-SC1:** MVP architecture supports up to 100 connected client accounts without infrastructure changes
- **NFR-SC2:** The polling job handles up to 10,000 payment events per client account per polling cycle
- **NFR-SC3:** The data model supports multi-user account expansion without schema migration of existing account or user records

### Data Retention

- **NFR-D1:** Payment event metadata is retained for 24 months from the event date, then automatically purged
- **NFR-D2:** Audit logs are retained for 36 months — longer than event data to satisfy compliance review windows
- **NFR-D3:** End-customer email addresses are purged within 30 days of a customer reaching Passive Churn status, unless the client account remains active and requests retention for win-back purposes
