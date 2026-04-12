# Sprint Change Proposal — Post-OAuth Profile Completion & Login Flow Fix

**Date:** 2026-04-12
**Triggered by:** Story 2.1 (User Registration & Stripe Connect OAuth)
**Proposed by:** John (PM) with security review by Winston (Architect)
**Scope classification:** Moderate — backlog addition with artifact updates

---

## 1. Issue Summary

### Problem Statement

Story 2.1 implemented Stripe OAuth as the sole registration path. The OAuth callback creates a `User` and `Account` record, but collects only an email address from Stripe. No mechanism exists for users to provide their name, company/SaaS name, or set a password.

### Impact

- **Broken identity:** `User.first_name` and `User.last_name` are always empty. WorkspaceIdentity displays "Workspace" instead of the user's name. UserMenu avatar shows "?" instead of initials.
- **Dead login path:** The login page has an email/password form that can never work — no password is ever set.
- **Downstream feature gaps:** Stories 4.2 (notification tone preview) and 5.4 (monthly savings email) reference "client's brand name" which has no collection mechanism.
- **No password recovery:** Users who close their browser cannot log back in without re-authorizing through Stripe.

### Evidence

- `User.first_name = ""` and `User.last_name = ""` after every OAuth registration
- `GET /account/me/` doesn't return name fields
- Login page `POST /auth/token/` requires password — but no password exists
- PRD references "Marc's workspace" (FR48, UX-DR6) but no FR specifies collecting Marc's name

### Discovery Context

Identified during Story 2.4 implementation when the dashboard shell showed empty workspace identity. Confirmed by auditing all 6 epics — no story addresses profile completion, name collection, or password setup.

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact | Details |
|------|--------|---------|
| **Epic 2** (current) | Add new story 2.1b | Profile completion + login fix. Insert after 2.1, before 2.5 |
| **Epic 3** | No changes | DPA flow (3.1) will display correctly once identity exists |
| **Epic 4** | Add new story 4.5 | Email-based password reset using Resend infrastructure |
| **Epic 5** | No changes | Monthly email will use company_name once populated |
| **Epic 6** | No changes | Operator console unaffected |

### Artifact Conflicts

| Artifact | Conflict | Resolution |
|----------|----------|------------|
| **PRD** | No FR for identity collection | Add FR49, amend FR1, add FR50 |
| **Architecture** | No `company_name` field, no profile endpoint, no password hashing config | Add field, endpoint, Argon2 config, rate limiting |
| **UX Spec** | Onboarding sequence missing profile step | Insert step between OAuth and dashboard |
| **Epics** | No story for profile completion or password reset | Add Story 2.1b and Story 4.5 |
| **Sprint Status** | Missing story entries | Add 2-1b and 4-5 entries |

### Technical Impact

- 1 new Django migration (`company_name` on Account)
- 1 new backend endpoint (`POST /api/v1/accounts/complete-profile/`)
- 1 new frontend page (`/register/complete`)
- 1 new dependency (`argon2-cffi`)
- Login page UX cleanup (clarify returning vs new user paths)
- `middleware.ts` update (redirect incomplete profiles)
- Existing `GET /account/me/` updated to return name fields

---

## 3. Recommended Approach

**Direct Adjustment** — add stories within existing epic structure.

### Rationale

- **Purely additive:** No rework of existing code. OAuth flow remains unchanged; profile completion is a new step after it.
- **Low effort:** Backend: 1 model field + 2 endpoints. Frontend: 1 new page + login page cleanup.
- **Low risk:** Standard form + API pattern already established in codebase.
- **High impact:** Unblocks workspace identity, notification branding, and email/password login.
- **Staged password recovery:** Stripe re-auth provides immediate fallback; full email reset deferred to Epic 4 when Resend is available.

### Effort & Risk

- **Effort:** Low (estimated 1 story point for 2.1b, 0.5 for 4.5)
- **Risk:** Low — no architectural changes, follows existing patterns
- **Timeline impact:** Adds ~1 story to Epic 2; does not delay Epic 3+ since 2.5 hasn't started

---

## 4. Detailed Change Proposals

### 4.1 PRD — Add FR49, FR50, Amend FR1

**File:** `_bmad-output/prd.md`

**Change 1 — Amend FR1 (line 461):**

OLD:
```
- **FR1:** A new user can connect their Stripe account to SafeNet via OAuth without handling API keys
```

NEW:
```
- **FR1:** A new user can connect their Stripe account to SafeNet via OAuth without handling API keys — after OAuth authorization, the user completes a one-time profile setup (name, company name, password) before reaching the dashboard
```

**Change 2 — Add FR49 and FR50 after FR48 (line 466):**

ADD after FR48:
```
- **FR49:** After Stripe Connect authorization, a new user must provide their full name, company/SaaS product name, and set a password before accessing the dashboard — this profile completion step is mandatory for first-time users and enables email/password login on subsequent visits
- **FR50:** A user who forgets their password can recover access via Stripe OAuth re-authentication on the login page; a full email-based password reset flow is available once the transactional email system is operational (Epic 4)
```

---

### 4.2 Epics — Add Story 2.1b

**File:** `_bmad-output/epics.md`

**INSERT after Story 2.1 (after line 401, before the `---` separator):**

```markdown

---

### Story 2.1b: Post-OAuth Profile Completion & Login Flow Fix

As a new founder who just connected Stripe,
I want to set my name, company name, and password before seeing the dashboard,
So that my workspace is personalized, emails reference my brand, and I can log in with email/password on future visits.

**Acceptance Criteria:**

**Given** a new user completes Stripe OAuth authorization
**When** the callback succeeds and a new account is created
**Then** the user is redirected to `/register/complete` (not the dashboard)
**And** they see a form collecting: first name, last name, company/SaaS name, and password with confirmation (FR49)

**Given** the profile completion form
**When** the user submits valid data
**Then** the User record is updated with `first_name`, `last_name`, and a hashed password (Argon2)
**And** the Account record is updated with `company_name`
**And** Django's full password validation suite is applied server-side (min 8 chars, common password check, similarity check)
**And** `password` and `password_confirm` are validated to match server-side
**And** the endpoint rejects repeat submissions with 400 if profile is already completed
**And** the profile completion is recorded in the audit log via `write_audit_event()`
**And** the user is redirected to the dashboard

**Given** a returning user who has completed profile setup
**When** they visit the login page
**Then** they can log in with email and password
**And** receive JWT tokens and are redirected to the dashboard

**Given** an existing user with a completed profile
**When** they click "Connect with Stripe" on the login page
**Then** the OAuth callback recognizes their account by `stripe_user_id`
**And** issues JWT tokens and redirects to the dashboard (no profile re-prompt)
**And** this serves as a password recovery fallback (FR50)

**Given** a user who completed OAuth but abandoned profile completion
**When** they return (via Stripe re-auth or any authenticated route)
**Then** they are redirected to `/register/complete` — profile setup cannot be bypassed

**Given** the login endpoint and profile completion endpoint
**When** either receives requests
**Then** rate limiting is enforced: 5/min on login, 3/min on profile completion

**Technical notes:**
- Add `argon2-cffi` dependency; configure `Argon2PasswordHasher` as primary in `PASSWORD_HASHERS`
- Add `company_name` CharField(max_length=200) to Account model + migration
- New endpoint: `POST /api/v1/accounts/complete-profile/` (JWT auth required)
- Update `GET /api/v1/accounts/me/` to return `first_name`, `last_name`, `company_name`
- DRF `ScopedRateThrottle` on auth and profile endpoints
- Frontend `middleware.ts` checks profile completion, redirects if incomplete
```

---

### 4.3 Epics — Add Story 4.5

**File:** `_bmad-output/epics.md`

**INSERT after Story 4.4 (after line 841, before the `---` separator before Epic 5):**

```markdown

---

### Story 4.5: Email-Based Password Reset Flow

As a founder who has forgotten my password,
I want to reset it via email,
So that I can regain access to my account without re-authorizing through Stripe.

**Acceptance Criteria:**

**Given** the login page
**When** a user clicks "Forgot password?"
**Then** they are prompted to enter their email address
**And** a password reset email is sent via Resend (same transactional email provider as notifications)
**And** the response is generic regardless of whether the email exists ("If an account exists, we've sent a reset link") — no email enumeration

**Given** a valid password reset email
**When** the user clicks the reset link
**Then** they are taken to a password reset form with a time-limited token (1 hour expiry, single-use)
**And** the token is generated via Django's `PasswordResetTokenGenerator` (no DB storage needed)

**Given** the password reset form
**When** the user submits a new password
**Then** the password is validated (same rules as profile completion: min 8 chars, Django validators)
**And** the password is updated and the reset token is invalidated
**And** the event is recorded in the audit log

**Given** password reset requests
**When** rate limiting is checked
**Then** a maximum of 3 reset requests per email per hour is enforced

**Technical notes:**
- Uses Resend infrastructure from Story 4.1
- Django's `PasswordResetTokenGenerator` for signed, time-limited tokens
- No additional DB models needed — tokens are stateless (signed with SECRET_KEY)
- Audit log: `action="password_reset_requested"` and `action="password_reset_completed"`
```

---

### 4.4 Architecture — Security Additions

**File:** `_bmad-output/architecture.md`

**INSERT after the "Client authentication" paragraph (after line 257):**

```markdown

**Password security:** `argon2-cffi` — Argon2id hashing (OWASP recommended, memory-hard). Configured as primary in `PASSWORD_HASHERS` with PBKDF2 as fallback for any legacy hashes. Django's `AUTH_PASSWORD_VALIDATORS` enabled: minimum 8 characters, common password rejection, user attribute similarity check, numeric-only rejection.

**Rate limiting:** DRF `ScopedRateThrottle` on authentication-sensitive endpoints:
- `auth` scope: 5 requests/min (login, token refresh)
- `profile` scope: 3 requests/min (profile completion)
- `password_reset` scope: 3 requests/email/hour (password reset requests)

**Profile completion endpoint:** `POST /api/v1/accounts/complete-profile/` — JWT auth required, one-time operation (rejects if `company_name` already set). Server-side validation of password match and strength. Audit logged via `write_audit_event()`.
```

**ADD `company_name` to Account model description (wherever Account model fields are listed):**

```
company_name  CharField(max_length=200, blank=True)  # SaaS/company name for workspace identity and notification branding
```

**ADD `argon2-cffi` to backend dependencies list.**

---

### 4.5 UX Spec — Add Profile Completion Screen

**File:** `_bmad-output/ux-design-specification.md`

**MODIFY onboarding sequence (lines 97-102):**

OLD:
```
1. Land on marketing site
2. Connect with Stripe (OAuth, one click)
3. Retroactive scan runs (animated, 8 seconds)
4. Dashboard populates — first insight delivered, no action required
```

NEW:
```
1. Land on marketing site
2. Connect with Stripe (OAuth, one click)
3. Profile completion: first name, last name, company/SaaS name, password
4. Redirect to dashboard (retroactive scan running in background)
5. Dashboard populates — first insight delivered, no action required
```

**ADD new screen specification (in the auth/onboarding screens section):**

```markdown
### Profile Completion Screen (/register/complete)

**Purpose:** Collect identity data after Stripe OAuth — mandatory one-time step before dashboard access.

**Layout:** Centered card (max-width 480px), SafeNet wordmark above, `--bg-base` background.

**Header:** "Almost there — tell us about you and your product."

**Fields:**
- First name (text input, required)
- Last name (text input, required)
- Company / SaaS name (text input, required, placeholder: "e.g., ProductivityPro")
- Password (password input, required, min 8 chars)
- Confirm password (password input, must match)

**CTA:** "Complete Setup" (primary button, `--cta` colour)

**Behaviour:**
- On success → redirect to dashboard
- Retroactive scan runs in background — dashboard handles its own loading state
- Cannot be skipped — middleware redirects incomplete profiles back here
- Validation errors shown inline per field

**Login page clarification:**
- Email/password form is primary (for returning users)
- Divider: "or"
- "Connect with Stripe" as secondary action (for new users or Stripe re-auth)
- Subtext: "New to SafeNet? Connect your Stripe account to get started"
- Add "Forgot password?" link below password field (links to reset flow when available, Epic 4)
```

---

### 4.6 Sprint Status — Add Story Entries

**File:** `_bmad-output/sprint-status.yaml`

**ADD after `2-1-user-registration-stripe-connect-oauth: done`:**
```yaml
  2-1b-post-oauth-profile-completion-login-fix: backlog
```

**ADD after `4-4-opt-out-mechanism-notification-suppression: backlog`:**
```yaml
  4-5-email-based-password-reset-flow: backlog
```

---

## 5. Implementation Handoff

### Scope Classification: Moderate

Backlog reorganization with artifact updates. No fundamental replan needed.

### Handoff Plan

| Role | Responsibility |
|------|---------------|
| **PM (John)** | Apply PRD edits (FR1, FR49, FR50) — done via this proposal |
| **SM (Bob)** | Update sprint-status.yaml, prioritize 2.1b before 2.5 |
| **Dev (create-story → dev-story)** | Implement Story 2.1b next. Story 4.5 deferred to Epic 4 execution |
| **Architect (Winston)** | Architecture doc security additions applied via this proposal |

### Success Criteria

- [ ] Profile completion screen collects name, company, password after OAuth
- [ ] Returning users can log in with email/password
- [ ] Existing users can log in via Stripe re-auth (password recovery fallback)
- [ ] WorkspaceIdentity shows real company name and user's name
- [ ] Rate limiting active on auth endpoints
- [ ] Argon2 password hashing configured
- [ ] All changes audit logged

### Priority & Sequencing

Story 2.1b should be implemented **before** Story 2.5 (subscription tiers). The upgrade flow benefits from having proper user identity. Story 4.5 is deferred to Epic 4 when Resend email infrastructure exists.
