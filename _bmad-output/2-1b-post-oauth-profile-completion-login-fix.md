# Story 2.1b: Post-OAuth Profile Completion & Login Flow Fix

Status: done

## Story

As a new founder who just connected Stripe,
I want to set my name, company name, and password before seeing the dashboard,
So that my workspace is personalized, emails reference my brand, and I can log in with email/password on future visits.

## Acceptance Criteria

1. **Given** a new user completes Stripe OAuth authorization **When** the callback succeeds and a new account is created **Then** the user is redirected to `/register/complete` (not the dashboard) **And** they see a form collecting: first name, last name, company/SaaS name, and password with confirmation (FR49)

2. **Given** the profile completion form **When** the user submits valid data **Then** the User record is updated with `first_name`, `last_name`, and a hashed password (Argon2) **And** the Account record is updated with `company_name` **And** Django's full password validation suite is applied server-side (min 8 chars, common password check, similarity check) **And** `password` and `password_confirm` are validated to match server-side **And** the endpoint rejects repeat submissions with 400 if profile is already completed **And** the profile completion is recorded in the audit log via `write_audit_event()` **And** the user is redirected to the dashboard

3. **Given** a returning user who has completed profile setup **When** they visit the login page **Then** they can log in with email and password **And** receive JWT tokens and are redirected to the dashboard

4. **Given** an existing user with a completed profile **When** they click "Connect with Stripe" on the login page **Then** the OAuth callback recognizes their account by `stripe_user_id` **And** issues JWT tokens and redirects to the dashboard (no profile re-prompt) **And** this serves as a password recovery fallback (FR50)

5. **Given** a user who completed OAuth but abandoned profile completion **When** they return (via Stripe re-auth or any authenticated route) **Then** they are redirected to `/register/complete` — profile setup cannot be bypassed

6. **Given** the login endpoint and profile completion endpoint **When** either receives requests **Then** rate limiting is enforced: 5/min on login, 3/min on profile completion

## Tasks / Subtasks

- [x] Task 1: Backend — Add `company_name` to Account model (AC: #2)
  - [x] 1.1 Add `company_name = models.CharField(max_length=200, blank=True, default="")` to `Account` model in `core/models/account.py`
  - [x] 1.2 Create and run migration: `python manage.py makemigrations core && python manage.py migrate`
  - [x] 1.3 Add `@property def profile_complete(self) -> bool` to Account: returns `bool(self.company_name and self.owner.first_name)`

- [x] Task 2: Backend — Configure Argon2 password hashing (AC: #2)
  - [x] 2.1 Add `argon2-cffi` to `pyproject.toml` via `poetry add argon2-cffi`
  - [x] 2.2 Add `PASSWORD_HASHERS` to `safenet_backend/settings/base.py`:
    ```python
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.Argon2PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    ]
    ```
  - [x] 2.3 Verify `AUTH_PASSWORD_VALIDATORS` already exists in `safenet_backend/settings/base.py` (lines 68-73) with the same four validators. No changes needed — Django's `MinimumLengthValidator` defaults to 8 chars already.

- [x] Task 3: Backend — Configure rate limiting (AC: #6)
  - [x] 3.1 Add to `REST_FRAMEWORK` settings in `base.py`:
    ```python
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "auth": "5/min",
        "profile": "3/min",
    },
    ```
  - [x] 3.2 Add `throttle_scope = "auth"` class attribute to `SafeNetTokenObtainPairView` in `core/views/auth.py`:
    ```python
    class SafeNetTokenObtainPairView(TokenObtainPairView):
        serializer_class = SafeNetTokenObtainPairSerializer
        throttle_scope = "auth"
    ```
  - [x] 3.3 Apply `throttle_scope = "profile"` to the profile completion view (Task 4)

- [x] Task 4: Backend — Profile completion endpoint (AC: #2)
  - [x] 4.1 Create `core/serializers/account.py` with `CompleteProfileSerializer`:
    - Fields: `first_name`, `last_name`, `company_name`, `password`, `password_confirm` (all required)
    - Validate `password == password_confirm`
    - Validate password strength via `django.contrib.auth.password_validation.validate_password()`
  - [x] 4.2 Create `complete_profile` view in `core/views/account.py`:
    - `POST /api/v1/account/complete-profile/`
    - `@permission_classes([IsAuthenticated])`
    - Guard: if `account.company_name` is non-empty, return `400 PROFILE_ALREADY_COMPLETED`
    - Update `user.first_name`, `user.last_name`, `user.set_password(password)`, `user.save()`
    - Update `account.company_name`, `account.save()`
    - Audit log: `write_audit_event(subscriber=None, actor="client", action="profile_completed", outcome="success", account=account)`
    - Return updated account data in `{data: {...}}` envelope
  - [x] 4.3 Wire in `core/urls.py`: `path("account/complete-profile/", account_views.complete_profile)`

- [x] Task 5: Backend — Update `account_detail` to return profile fields (AC: #2, #5)
  - [x] 5.1 Update `GET /api/v1/account/me/` response in `core/views/account.py` to include:
    ```python
    "owner": {
        "id": request.user.id,
        "email": request.user.email,
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
    },
    "company_name": account.company_name,
    "profile_complete": account.profile_complete,
    ```
  - [x] 5.2 Keep backward compatibility: retain `owner_email` field alongside new `owner` object

- [x] Task 6: Backend — Update OAuth callback redirect logic (AC: #1, #4)
  - [x] 6.1 In `core/views/stripe.py` `stripe_connect_callback`: add `is_new_account` flag to response:
    ```python
    "is_new_account": is_new_account,
    "profile_complete": account.profile_complete,
    ```
  - [x] 6.2 For existing users (reconnection path): ensure JWT tokens are issued and `profile_complete` is returned — no profile re-prompt if already completed

- [x] Task 7: Backend tests (AC: all)
  - [x] 7.1 Test `complete_profile` endpoint: valid submission updates User + Account
  - [x] 7.2 Test `complete_profile` rejects repeat submission (400)
  - [x] 7.3 Test `complete_profile` rejects weak password (Django validators)
  - [x] 7.4 Test `complete_profile` rejects mismatched passwords
  - [x] 7.5 Test `complete_profile` requires authentication (401 without JWT)
  - [x] 7.6 Test `account_detail` returns profile fields
  - [x] 7.7 Test rate limiting on login endpoint (6th request within 1 min returns 429)
  - [x] 7.8 Test Stripe callback returns `is_new_account` and `profile_complete` flags
  - [x] 7.9 Test Argon2 is used for password hashing (check `user.password` starts with `argon2`)
  - [x] 7.10 Test audit log entry created on profile completion

- [x] Task 8: Frontend — Update TypeScript types (AC: #2)
  - [x] 8.1 Update `src/types/account.ts`: add `company_name: string` and `profile_complete: boolean` to `Account` interface. Note: `owner: User` nesting already exists in the type — no change needed for that field.
  - [x] 8.2 Create `src/types/auth.ts`: `CompleteProfileRequest` interface with `first_name`, `last_name`, `company_name`, `password`, `password_confirm`

- [x] Task 9: Frontend — Profile completion page (AC: #1, #2)
  - [x] 9.1 Create `src/app/(auth)/register/complete/page.tsx`
  - [x] 9.2 Centered card layout (max-width 480px), SafeNet wordmark, `--bg-base` background
  - [x] 9.3 Header: "Almost there — tell us about you and your product."
  - [x] 9.4 Form fields: first name, last name, company/SaaS name (placeholder: "e.g., ProductivityPro"), password, confirm password
  - [x] 9.5 Submit button: "Complete Setup" using `--cta` colour
  - [x] 9.6 On submit: `POST /api/v1/account/complete-profile/` via api client
  - [x] 9.7 On success: `router.replace(ROUTES.DASHBOARD)`
  - [x] 9.8 Inline validation errors per field from API response
  - [x] 9.9 Password strength feedback (min 8 chars hint)

- [x] Task 10: Frontend — Update OAuth callback redirect (AC: #1, #4)
  - [x] 10.1 Update `src/app/(auth)/register/callback/page.tsx`:
    - Update the TypeScript generic type to include new fields: `{ data: { access: string; refresh: string; account_id: number; is_new_account: boolean; profile_complete: boolean } }`
    - After storing tokens, check `response.data.data.profile_complete`
    - If `false` (new account): redirect to `/register/complete`
    - If `true` (reconnection): redirect to `/dashboard`
  - [x] 10.2 Add `REGISTER_COMPLETE: "/register/complete"` to `src/lib/constants.ts` ROUTES

- [x] Task 11: Frontend — Update middleware for profile completion guard (AC: #5)
  - [x] 11.1 Update `src/middleware.ts`:
    - Note: `/register/complete` is already excluded by the middleware matcher regex (all `/register/*` paths are skipped) — no `PUBLIC_PATHS` change needed
    - For authenticated requests to dashboard routes: check a `safenet_profile_complete` cookie
    - If cookie is missing/false: redirect to `/register/complete`
  - [x] 11.2 Set `safenet_profile_complete` cookie on profile completion success (from the complete page)
  - [x] 11.3 Alternatively: the profile completion page can check `useAccount().profile_complete` and redirect to dashboard if already complete

- [x] Task 12: Frontend — Login page cleanup (AC: #3, #4)
  - [x] 12.1 Update `src/app/(auth)/login/page.tsx`:
    - Email/password form remains primary (for returning users)
    - Add "Forgot password?" link below password field (disabled/placeholder until Epic 4)
    - "Connect with Stripe" section: update subtext to "New to SafeNet? Connect your Stripe account to get started"
    - Clarify visual hierarchy: email/password is for returning users, Stripe is for new/recovery

- [x] Task 13: Frontend tests (AC: all)
  - [x] 13.1 Test profile completion page renders form fields
  - [x] 13.2 Test form submission calls correct API endpoint
  - [x] 13.3 Test validation errors display inline
  - [x] 13.4 Test redirect to dashboard on success
  - [x] 13.5 Test callback page redirects to `/register/complete` for new accounts

## Dev Notes

### Architecture Compliance

- **Backend model location:** `core/models/account.py` — add `company_name` field to existing `Account` model [Source: architecture.md#Account Model]
- **Backend view location:** `core/views/account.py` — add `complete_profile` view alongside existing `account_detail` [Source: architecture.md#Views Organization]
- **Backend serializer:** `core/serializers/account.py` — new file, follows existing serializer pattern [Source: architecture.md#Backend Structure]
- **Frontend page location:** `src/app/(auth)/register/complete/page.tsx` — new page in auth route group [Source: architecture.md#Frontend Auth Routes]
- **API response:** `{data: {...}}` envelope — never bare root objects [Source: architecture.md#API Response Envelope]
- **Monetary values:** N/A for this story
- **TypeScript fields:** snake_case matching API — no camelCase transformation [Source: architecture.md#TypeScript Type Naming]
- **Audit logging:** Use `write_audit_event()` — never inline [Source: architecture.md#Audit Log Write]
- **Password hashing:** Argon2id via `argon2-cffi` [Source: architecture.md#Password Security]
- **Rate limiting:** DRF `ScopedRateThrottle` [Source: architecture.md#Rate Limiting]

### Technical Requirements

- **Argon2:** `argon2-cffi` must be added via `poetry add argon2-cffi` (project uses Poetry, not pip)
- **Migration:** `company_name` field is `blank=True, default=""` — safe to add without data migration
- **Profile guard logic:** The `profile_complete` property on Account checks `company_name` and `first_name` are non-empty. This is returned by `/account/me/` and `/stripe/callback/` so both frontend middleware and callback can make routing decisions.
- **Password validation:** Use Django's `validate_password()` which runs all configured validators — don't reimplement
- **Throttle scope:** Applied via `throttle_scope` class attribute on views, not decorators

### Existing Code to Modify

**Backend files to modify:**
- `backend/core/models/account.py` — add `company_name` field + `profile_complete` property
- `backend/core/views/account.py` — add `complete_profile` view, update `account_detail` response
- `backend/core/views/auth.py` — add `throttle_scope = "auth"` to token view
- `backend/core/views/stripe.py` — add `is_new_account` and `profile_complete` to callback response
- `backend/core/urls.py` — add route for `complete-profile`
- `backend/safenet_backend/settings/base.py` — add `PASSWORD_HASHERS`, throttle config (`AUTH_PASSWORD_VALIDATORS` already exists)
- `backend/pyproject.toml` — add `argon2-cffi` dependency

**Frontend files to modify:**
- `frontend/src/app/(auth)/register/callback/page.tsx` — redirect based on `profile_complete`
- `frontend/src/app/(auth)/login/page.tsx` — UX cleanup, add "Forgot password?" placeholder
- `frontend/src/middleware.ts` — add profile completion guard
- `frontend/src/types/account.ts` — add `company_name`, `profile_complete`, nested `owner`
- `frontend/src/lib/constants.ts` — add `REGISTER_COMPLETE` route

### New Files

- `backend/core/serializers/account.py` — `CompleteProfileSerializer`
- `backend/tests/test_api/test_profile.py` — profile completion tests
- `frontend/src/app/(auth)/register/complete/page.tsx` — profile completion page
- `frontend/src/types/auth.ts` — `CompleteProfileRequest` interface
- `frontend/src/__tests__/ProfileComplete.test.tsx` — profile page tests

### Previous Story Intelligence (Story 2.1)

**Critical: do not break existing patterns:**
- `views/stripe.py` uses `transaction.atomic()` for account creation — changes are additive only
- `is_new_account` flag already exists in callback logic — just expose it in the response
- 111 backend tests exist — run full suite after changes

**Existing code to reuse:**
- `src/lib/api.ts` — axios instance with JWT interceptor
- `src/lib/auth.ts` — `setTokens()`, `clearTokens()`
- `src/hooks/useAccount.ts` — TanStack Query hook for `/account/me/`
- `src/components/ui/input.tsx`, `src/components/ui/button.tsx` — shadcn form components
- `src/lib/constants.ts` — route constants
- `core/services/audit.py` — `write_audit_event()` helper

### API Contracts

**POST `/api/v1/account/complete-profile/`** (JWT required)

Request:
```json
{
  "first_name": "Marc",
  "last_name": "Dupont",
  "company_name": "ProductivityPro",
  "password": "securepass123",
  "password_confirm": "securepass123"
}
```

Success response (200):
```json
{
  "data": {
    "id": 1,
    "owner": {
      "id": 1,
      "email": "marc@example.com",
      "first_name": "Marc",
      "last_name": "Dupont"
    },
    "company_name": "ProductivityPro",
    "tier": "mid",
    "trial_ends_at": "2026-05-12T00:00:00Z",
    "is_on_trial": true,
    "stripe_connected": true,
    "profile_complete": true,
    "created_at": "2026-04-12T12:00:00Z"
  }
}
```

Error responses:
```json
// 400 — Profile already completed
{"error": {"code": "PROFILE_ALREADY_COMPLETED", "message": "Profile has already been set up.", "field": null}}

// 400 — Password mismatch
{"error": {"code": "VALIDATION_ERROR", "message": "Passwords do not match.", "field": "password_confirm"}}

// 400 — Weak password
{"error": {"code": "VALIDATION_ERROR", "message": "This password is too common.", "field": "password"}}

// 429 — Rate limited
{"error": {"code": "THROTTLED", "message": "Request was throttled.", "field": null}}
```

**Updated GET `/api/v1/account/me/`** response:
```json
{
  "data": {
    "id": 1,
    "owner_email": "marc@example.com",
    "owner": {
      "id": 1,
      "email": "marc@example.com",
      "first_name": "Marc",
      "last_name": "Dupont"
    },
    "company_name": "ProductivityPro",
    "tier": "mid",
    "trial_ends_at": "2026-05-12T00:00:00Z",
    "is_on_trial": true,
    "stripe_connected": true,
    "profile_complete": true,
    "created_at": "2026-04-12T12:00:00Z"
  }
}
```

**Updated POST `/api/v1/stripe/callback/`** response (add fields):
```json
{
  "data": {
    "access": "eyJ...",
    "refresh": "eyJ...",
    "account_id": 1,
    "is_new_account": true,
    "profile_complete": false
  }
}
```

### Anti-Pattern Prevention

- **DO NOT** store passwords in plain text — always `user.set_password()` which hashes via Argon2
- **DO NOT** validate passwords client-side only — server-side validation is mandatory
- **DO NOT** allow profile completion endpoint to be called repeatedly — guard with `company_name` check
- **DO NOT** redirect new users directly to dashboard — always go through `/register/complete` first
- **DO NOT** break the existing OAuth flow — changes to `stripe.py` callback are additive (new response fields only)
- **DO NOT** use `useState` for server data — `useAccount` hook (TanStack Query) already handles account data
- **DO NOT** add `argon2-cffi` via pip — use `poetry add argon2-cffi` (project uses Poetry)
- **DO NOT** skip running the full backend test suite — 111 existing tests must continue passing

### Project Structure Notes

- All paths align with monorepo structure: `backend/` for Django, `frontend/` for Next.js
- The profile completion page is in `(auth)` route group — not `(dashboard)` — because the user hasn't completed onboarding yet
- `/register/complete` must be accessible with a valid JWT but before profile is complete — middleware needs to allow this path

### References

- [Source: sprint-change-proposal-2026-04-12.md] — Full change proposal with security review
- [Source: architecture.md#Authentication & Security] — JWT, Argon2, rate limiting specs
- [Source: architecture.md#Profile completion endpoint] — Endpoint contract
- [Source: architecture.md#API Response Envelope] — `{data: {...}}` format
- [Source: architecture.md#Audit Log Write] — `write_audit_event()` pattern
- [Source: ux-design-specification.md#Onboarding sequence] — Step 3 is profile completion
- [Source: prd.md#FR49] — Profile completion requirement
- [Source: prd.md#FR50] — Password recovery via Stripe re-auth
- [Source: epics.md#Story 2.1b] — Full acceptance criteria
- [Source: 2-1-user-registration-stripe-connect-oauth.md] — Previous story implementation details

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- Throttle test initially caused rate-limit interference with existing JWT tests; resolved by clearing Django cache before/after throttle test
- Docker rebuild required after adding argon2-cffi to install the dependency in the container

### Completion Notes List
- Task 1: Added `company_name` field and `profile_complete` property to Account model; migration created (0005)
- Task 2: Added `argon2-cffi` via Poetry; configured `PASSWORD_HASHERS` with Argon2 as primary hasher
- Task 3: Added `ScopedRateThrottle` config (5/min auth, 3/min profile); applied throttle_scope to token view and profile view
- Task 4: Created `CompleteProfileSerializer` and `complete_profile` endpoint with guard, password validation, audit logging
- Task 5: Updated `account_detail` to return `owner` object, `company_name`, `profile_complete`; kept `owner_email` for backward compat
- Task 6: Added `is_new_account` and `profile_complete` to Stripe callback response
- Task 7: 10 backend tests covering profile completion, account detail, rate limiting, Argon2 hashing, audit log
- Task 8: Updated Account type with `company_name`, `profile_complete`; created `CompleteProfileRequest` type
- Task 9: Created profile completion page with all form fields, inline errors, password hint, CTA button
- Task 10: Updated callback to redirect to `/register/complete` for new accounts, `/dashboard` for returning users
- Task 11: Added profile completion guard to middleware; sets `safenet_profile_complete` cookie
- Task 12: Added disabled "Forgot password?" placeholder; updated Stripe section subtext
- Task 13: 6 frontend tests covering form rendering, API call, validation errors, redirect behavior, callback redirect logic

### Change Log
- 2026-04-12: Implemented story 2-1b — all 13 tasks complete, 160 backend tests pass, 38 frontend tests pass

### File List
**New files:**
- backend/core/migrations/0005_add_company_name_to_account.py
- backend/core/serializers/account.py
- backend/core/tests/test_api/test_profile.py
- frontend/src/app/(auth)/register/complete/page.tsx
- frontend/src/types/auth.ts
- frontend/src/__tests__/ProfileComplete.test.tsx
- frontend/src/__tests__/StripeCallback.test.tsx

**Modified files:**
- backend/core/models/account.py
- backend/core/views/account.py
- backend/core/views/auth.py
- backend/core/views/stripe.py
- backend/core/urls.py
- backend/safenet_backend/settings/base.py
- backend/pyproject.toml
- backend/poetry.lock
- frontend/src/types/account.ts
- frontend/src/types/index.ts
- frontend/src/app/(auth)/register/callback/page.tsx
- frontend/src/app/(auth)/login/page.tsx
- frontend/src/middleware.ts
- frontend/src/lib/constants.ts

### Review Findings

#### Decision Needed (resolved)
- [x] [Review][Decision] **Cookie-based profile guard is trivially forgeable** — Resolved: (A) backend proxy now sets httpOnly cookie. Removed all client-side `document.cookie` calls. Proxy parses JSON response and sets `safenet_profile_complete` as httpOnly/Secure/SameSite=Lax. Added `profile_complete` to login token response.
- [x] [Review][Decision] **`profile_complete` property does not check `has_usable_password()`** — Resolved: (B) added `self.owner.has_usable_password()` to `Account.profile_complete` property.

#### Patch (fixed)
- [x] [Review][Patch] **Non-atomic user+account save creates split-brain state** — Fixed: wrapped in `transaction.atomic()`. [backend/core/views/account.py]
- [x] [Review][Patch] **Race condition on profile completion idempotency guard** — Fixed: added `select_for_update()` inside atomic block with re-check. [backend/core/views/account.py]
- [x] [Review][Patch] **Idempotency guard misaligned with `profile_complete` property** — Fixed: guard now uses `account.profile_complete` instead of `account.company_name`. [backend/core/views/account.py]
- [x] [Review][Patch] **`/register/complete` page accessible without authentication** — Fixed: page now uses `useAccount()` which triggers 401→login redirect for unauthenticated users. [frontend/src/app/(auth)/register/complete/page.tsx]
- [x] [Review][Patch] **CompleteProfilePage never verifies server-side profile status** — Fixed: added `useAccount()` hook + `useEffect` guard that redirects to dashboard if `profile_complete` is already true. [frontend/src/app/(auth)/register/complete/page.tsx]
- [x] [Review][Patch] **Throttle scope set via `initkwargs` mutation — fragile** — Fixed: replaced with `_ProfileThrottle(ScopedRateThrottle)` subclass with `scope = "profile"`, used via `@throttle_classes`. [backend/core/views/account.py]
- [x] [Review][Patch] **Cookie string with magic number repeated in 3 files** — Fixed: all three `document.cookie` calls removed. Cookie now set exclusively by the proxy with consistent attributes. [frontend proxy route.ts]

#### Deferred (pre-existing, not introduced by this change)
- [x] [Review][Defer] **`ScopedRateThrottle` in `DEFAULT_THROTTLE_CLASSES` silently passes endpoints without a `throttle_scope`** — `AllowAny` endpoints like `initiate_stripe_connect` and `stripe_connect_callback` have no rate limiting. An attacker could flood the cache with state tokens or exhaust DB connections. [backend/safenet_backend/settings/base.py:103] — deferred, pre-existing
- [x] [Review][Defer] **`stripe.error.StripeError` may not exist in Stripe SDK v15** — `backend/core/views/stripe.py:93` catches `stripe.error.StripeError` but Stripe v15 moved exceptions to `stripe.StripeError`. Falls through to generic exception handler. [backend/core/views/stripe.py:93] — deferred, pre-existing
