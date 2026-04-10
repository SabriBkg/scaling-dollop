# Story 2.3: Authenticated Dashboard Shell & Navigation

Status: done

## Story

As an authenticated founder,
I want a persistent, responsive dashboard layout with always-visible engine status and workspace identity,
so that I always know SafeNet is running and can navigate confidently between sections.

## Acceptance Criteria

1. **Top Navigation Bar** (UX-DR6, UX-DR5)
   - Given an authenticated user loads any dashboard page
   - When the page renders
   - Then the top navigation bar is visible (48px height) with:
     - `WorkspaceIdentity`: SafeNet wordmark + vertical divider + 2-letter SaaS monogram + SaaS name + "Marc's workspace"
     - `EngineStatusIndicator` (right-anchored)
     - User account menu (far right)
   - And navigation tabs link to: Dashboard, Settings (and Review Queue when in Supervised mode)

2. **EngineStatusIndicator Behavior** (UX-DR5, UX-DR13)
   - Given the `EngineStatusIndicator`
   - When the engine is active (Autopilot or Supervised)
   - Then it displays: animated blue pulse dot + "Autopilot active" or "Supervised" + "Last scan Xm ago · next in Ym"
   - And when paused: grey static dot + "Paused" text
   - And when errored: amber dot + error status text
   - And status changes are announced via `aria-live="polite"`

3. **Responsive Viewport Handling** (UX-DR14)
   - Given a desktop viewport (>=1280px): full layout, 48px topbar, main content max-width 1280px with 32px padding
   - Given tablet (768-1023px): layout adapts, single-column Story Arc
   - Given mobile (<768px): top nav visible, read-only view only, complex actions (batch review, DPA signing) NOT accessible

4. **Theme Toggle** (UX-DR1)
   - Given the light/dark theme toggle in top nav
   - When the user switches theme
   - Then all CSS custom properties update instantly via `.dark` class on root element
   - And the preference is persisted in `uiStore` and applied on next load

5. **Protected Route Enforcement**
   - Given an unauthenticated user navigates to any dashboard route
   - Then they are redirected to `/register` (already handled by middleware.ts)

## Tasks / Subtasks

- [x] Task 1: Create `WorkspaceIdentity` component (AC: #1)
  - [x] 1.1 Build `src/components/common/WorkspaceIdentity.tsx` with SafeNet wordmark, vertical divider, 2-letter monogram, SaaS name, owner label
  - [x] 1.2 Use `useAccount` hook for owner name; hardcode "SafeNet" as product name for now
  - [x] 1.3 Add loading skeleton state

- [x] Task 2: Create `EngineStatusIndicator` component (AC: #2)
  - [x] 2.1 Build `src/components/common/EngineStatusIndicator.tsx`
  - [x] 2.2 Implement animated pulse dot (blue=active, grey=paused, amber=error) using Tailwind `motion-safe:animate-pulse` with `prefers-reduced-motion` respect
  - [x] 2.3 Display status text + timing ("Last scan Xm ago · next in Ym")
  - [x] 2.4 Add `aria-live="polite"` for status change announcements
  - [x] 2.5 Stub engine status from `useEngineStatus()` hook returning mock data (paused, null timestamps)

- [x] Task 3: Create `NavBar` component with navigation tabs (AC: #1)
  - [x] 3.1 Build `src/components/common/NavBar.tsx` with horizontal top navigation
  - [x] 3.2 Tabs: "Dashboard" (links to `/dashboard`), "Settings" (links to `/settings`)
  - [x] 3.3 Conditionally render "Review Queue" tab when engine mode is Supervised (via `useEngineStatus`)
  - [x] 3.4 Active tab: font-semibold + 2px bottom border in accent-active; inactive: muted text
  - [x] 3.5 Integrate `WorkspaceIdentity` (left), navigation tabs (center), `EngineStatusIndicator` + theme toggle + user menu (right)

- [x] Task 4: Create `ThemeToggle` component (AC: #4)
  - [x] 4.1 Build `src/components/common/ThemeToggle.tsx` using `next-themes` `useTheme()` hook
  - [x] 4.2 Toggle between light/dark — persist preference via `uiStore.setThemePreference()`
  - [x] 4.3 Use Sun/Moon icons from `lucide-react`

- [x] Task 5: Create `UserMenu` component (AC: #1)
  - [x] 5.1 Build `src/components/common/UserMenu.tsx` with avatar/initials + dropdown
  - [x] 5.2 Menu items: Account settings link, Logout action
  - [x] 5.3 Logout calls `DELETE /api/auth/login` to clear cookies, then `authStore.clearAuth()`, then redirect to `/login`
  - [x] 5.4 Use shadcn `DropdownMenu` component (added via `npx shadcn@latest add dropdown-menu`)

- [x] Task 6: Implement dashboard layout shell (AC: #1, #3)
  - [x] 6.1 Update `src/app/(dashboard)/layout.tsx` to render `NavBar` + main content area
  - [x] 6.2 Main content: `max-w-[1280px] mx-auto px-8` (32px padding)
  - [x] 6.3 Topbar fixed height: `h-12` (48px)
  - [x] 6.4 Responsive breakpoints: full at `lg:` (>=1024px), adapted at `md:`, single-column at default

- [x] Task 7: Create `/settings` page stub (AC: #1)
  - [x] 7.1 Create `src/app/(dashboard)/settings/page.tsx` with placeholder content
  - [x] 7.2 Ensure it renders inside the dashboard layout shell

- [x] Task 8: Add `useAccount` hook for fetching account data (AC: #1, #2)
  - [x] 8.1 Create `src/hooks/useAccount.ts` — TanStack Query hook calling `GET /api/v1/accounts/me/`
  - [x] 8.2 Returns account data including tier, stripe_connected, owner info
  - [x] 8.3 Used by WorkspaceIdentity for SaaS name and NavBar for mode-conditional tabs

## Dev Notes

### Architecture Compliance

- **Component location:** All new components go in `src/components/common/` (shared across pages)
- **File naming:** PascalCase for components (`NavBar.tsx`), camelCase for hooks (`useAccount.ts`)
- **One component per file** — no multi-component files
- **State management:** Use TanStack Query for server data (`useAccount`), Zustand for UI state (`uiStore`)
- **Styling:** Tailwind CSS utility classes only. Use SafeNet design tokens from `globals.css` (e.g., `text-[var(--text-primary)]`, `bg-[var(--bg-base)]`)
- **API fields:** All snake_case — no camelCase transformation. TypeScript types mirror API exactly.
- **shadcn/ui:** Use existing primitives from `src/components/ui/`. If a new primitive is needed (e.g., DropdownMenu), add it via `npx shadcn@latest add dropdown-menu`

### Design Token Reference

Already defined in `src/app/globals.css` — DO NOT redefine:

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--bg-base` | #F8F9FC | #0F1117 | Page background |
| `--bg-surface` | #FFFFFF | #1A1D27 | Cards, nav bar |
| `--bg-elevated` | #FFFFFF | #242736 | Hover states |
| `--sn-border` | #E2E5EF | #2D3148 | Dividers, borders |
| `--text-primary` | #0F1117 | #F9FAFB | Headlines, key data |
| `--text-secondary` | #4B5563 | #9CA3AF | Labels, supporting copy |
| `--text-tertiary` | #9CA3AF | #6B7280 | Timestamps |
| `--accent-active` | #3B82F6 | #60A5FA | Engine running, active state |
| `--accent-recovery` | #10B981 | #10B981 | Recovered amounts |
| `--accent-fraud` | #EF4444 | #F87171 | Fraud flags only |
| `--cta` | #3B82F6 | #60A5FA | Primary action |

### Typography (Inter font, already configured)

| Level | Size | Weight | Usage |
|-------|------|--------|-------|
| H1 | 24px | 600 | Page titles |
| H2 | 20px | 600 | Section headers |
| Body | 15px | 400 | Primary content |
| Small | 13px | 400 | Supporting copy, metadata |
| Label | 12px | 500 | Status badges, column headers |

### Topbar Layout Spec

```
[WorkspaceIdentity] ---- [Dashboard] [Settings] [Review Queue?] ---- [EngineStatus] [ThemeToggle] [UserMenu]
 left-anchored              center navigation tabs                      right-anchored cluster
```

- Height: 48px (`h-12`)
- Background: `--bg-surface` with 1px bottom border `--sn-border`
- Max content width: 1280px centered
- Padding: 16px horizontal

### EngineStatusIndicator States

| State | Dot Color | Dot Animation | Text | Subtext |
|-------|-----------|---------------|------|---------|
| Active (Autopilot) | `--accent-active` (blue) | `animate-pulse` | "Autopilot active" | "Last scan Xm ago · next in Ym" |
| Active (Supervised) | `--accent-active` (blue) | `animate-pulse` | "Supervised" | "Last scan Xm ago · next in Ym" |
| Paused | `--accent-neutral` (grey) | none | "Paused" | — |
| Error | amber (#F59E0B) | none | "Error" | error detail |

**Accessibility:** `aria-label="Engine status: Autopilot active, last scan 18 minutes ago"` on the container, `aria-live="polite"` for dynamic updates.

**Reduced motion:** Wrap pulse animation in `@media (prefers-reduced-motion: no-preference)` or use Tailwind `motion-safe:animate-pulse`.

### Responsive Behavior

| Breakpoint | Layout |
|-----------|--------|
| Desktop (>=1280px) | Full topbar + main content (max 1280px, 32px padding) |
| Tablet (768-1023px) | Topbar adapts — may hide engine subtext, compact nav |
| Mobile (<768px) | Topbar visible, navigation simplified, read-only dashboard |

- Story Arc 3-column layout (Story 2.4) NEVER renders below `lg:` breakpoint
- Mobile disables batch review and DPA signing actions
- All font sizes use `rem` units

### Existing Code to Reuse — DO NOT Recreate

| What | Path | Notes |
|------|------|-------|
| Axios API client | `src/lib/api.ts` | Pre-configured with cookie auth + 401 interceptor |
| Auth store | `src/stores/authStore.ts` | `user`, `isAuthenticated`, `setUser`, `clearAuth` |
| UI store | `src/stores/uiStore.ts` | `themePreference`, `setThemePreference`, batch selection |
| Types | `src/types/account.ts` | `User`, `Account`, `StripeConnection`, `AuthTokens` |
| API response types | `src/types/index.ts` | `ApiResponse<T>`, `ApiError` |
| Formatters | `src/lib/formatters.ts` | `formatCurrency`, `formatDate`, `formatRelativeTime` |
| Route constants | `src/lib/constants.ts` | `ROUTES.DASHBOARD`, `ROUTES.LOGIN`, etc. |
| shadcn components | `src/components/ui/*` | button, card, badge, popover, sheet, separator, etc. |
| next-themes | already in package.json | Use `useTheme()` hook for theme switching |
| lucide-react | already in package.json | Sun, Moon, ChevronDown, Settings, LogOut icons |
| Middleware | `src/middleware.ts` | Already protects non-public routes — no changes needed |

### API Endpoint for Account Data

Create a `useAccount` hook that calls: `GET /api/v1/accounts/me/`

Expected response shape (matches existing `Account` type):
```json
{
  "data": {
    "id": 1,
    "owner": { "id": 1, "email": "marc@example.com", "first_name": "Marc", "last_name": "B" },
    "tier": "mid",
    "trial_ends_at": "2026-05-06T00:00:00Z",
    "is_on_trial": true,
    "stripe_connected": true,
    "created_at": "2026-04-06T12:00:00Z"
  }
}
```

**Note:** If this endpoint doesn't exist on the backend yet, the hook should still be implemented with TanStack Query and will work once the endpoint is available. Use `staleTime: 5 * 60 * 1000` (5 min).

### Engine Status — Stub Strategy

The engine status API does not exist yet (comes in Story 3.1+). Create `src/hooks/useEngineStatus.ts` that returns a **stubbed/mock response** for now:

```typescript
// Stub until engine status API exists (Story 3.1+)
type EngineStatus = {
  mode: "autopilot" | "supervised" | "paused" | "error";
  last_scan_at: string | null;
  next_scan_at: string | null;
};
```

Return `{ mode: "paused", last_scan_at: null, next_scan_at: null }` as default. The EngineStatusIndicator should render correctly for all states so it's ready when the API arrives.

### Previous Story Intelligence

**From Story 2.2 (completed):**
- Backend models `Subscriber`, `SubscriberFailure` exist with scan/poll tasks
- Celery beat runs `poll_new_failures` hourly — this is what drives engine status timing
- `failure_ingestion.py` service handles shared logic — don't duplicate
- All tests use pytest + pytest-django; frontend tests not yet established

**From Story 2.1 (completed):**
- Auth flow fully working: Stripe OAuth -> cookie bridge -> httpOnly tokens
- Middleware protects all non-public routes
- `authStore` populated after login, cleared on logout
- Logout must call `DELETE /api/auth/login` to clear server-side cookies

### Git Intelligence

Recent commits established these patterns:
- Frontend uses `"use client"` directive for interactive components
- Root layout wraps children in `<Providers>` (TanStack Query + next-themes)
- `(auth)` and `(dashboard)` route groups are established
- Dashboard route is at `/dashboard` (not `/`)

### Project Structure Notes

- The `(dashboard)/layout.tsx` is the target file for the shell — currently a passthrough stub
- Add new routes as subdirectories under `(dashboard)/` (e.g., `(dashboard)/settings/page.tsx`)
- Update `ROUTES` in `src/lib/constants.ts` if adding new route paths
- Placeholder directories `common/`, `dashboard/`, `settings/`, `subscriber/` already exist under `components/`

### References

- [Source: _bmad-output/epics.md — Epic 2, Story 2.3]
- [Source: _bmad-output/architecture.md — Frontend Architecture, Component Organization, State Management]
- [Source: _bmad-output/ux-design-specification.md — Dashboard Shell, Navigation, Design Tokens, Responsive Breakpoints, EngineStatusIndicator, WorkspaceIdentity]
- [Source: _bmad-output/2-2-90-day-retroactive-scan-background-job.md — Previous Story Intelligence]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Fixed shadcn dropdown-menu compatibility: base-ui v1.3 Trigger does not support `asChild` prop (unlike Radix). Applied inline styling to trigger element directly.
- Installed happy-dom for vitest test environment (jsdom v27 has ESM-only dependencies incompatible with vitest forks pool).

### Completion Notes List

- All 8 tasks implemented and verified with passing tests (14 tests across 5 test files)
- TypeScript compilation passes clean (zero errors)
- ESLint passes clean
- Frontend test infrastructure established: vitest + @testing-library/react + happy-dom
- WorkspaceIdentity uses useAccount hook (not useAuthStore) for owner data since account endpoint provides richer info
- Review Queue tab conditionally shown based on engine mode === "supervised" (via useEngineStatus stub)
- EngineStatusIndicator uses motion-safe:animate-pulse for prefers-reduced-motion compliance
- All components follow project conventions: "use client" directive, Tailwind with design tokens, one component per file

### Change Log

- 2026-04-10: Story 2.3 implemented — all 8 tasks complete, 14 tests passing

### File List

- frontend/src/hooks/useAccount.ts (new)
- frontend/src/hooks/useEngineStatus.ts (new)
- frontend/src/components/common/WorkspaceIdentity.tsx (new)
- frontend/src/components/common/EngineStatusIndicator.tsx (new)
- frontend/src/components/common/NavBar.tsx (new)
- frontend/src/components/common/ThemeToggle.tsx (new)
- frontend/src/components/common/UserMenu.tsx (new)
- frontend/src/components/ui/dropdown-menu.tsx (new — added via shadcn CLI)
- frontend/src/app/(dashboard)/layout.tsx (modified)
- frontend/src/app/(dashboard)/settings/page.tsx (new)
- frontend/src/lib/constants.ts (modified — added SETTINGS route)
- frontend/src/__tests__/setup.ts (new)
- frontend/src/__tests__/useEngineStatus.test.ts (new)
- frontend/src/__tests__/WorkspaceIdentity.test.tsx (new)
- frontend/src/__tests__/EngineStatusIndicator.test.tsx (new)
- frontend/src/__tests__/ThemeToggle.test.tsx (new)
- frontend/src/__tests__/NavBar.test.tsx (new)
- frontend/vitest.config.mts (new)
- frontend/package.json (modified — added test deps and scripts)

### Review Findings

- [x] [Review][Defer] Mobile navigation inaccessible below `md:` breakpoint — Nav tabs use `hidden md:flex` with no hamburger or fallback. Deferred: mobile is read-only MVP; dedicated mobile nav story preferred.
- [x] [Review][Patch] ThemeToggle missing `mounted` guard for SSR hydration — fixed: added mounted state guard
- [x] [Review][Patch] `clearTokens()` failure silently breaks logout — fixed: wrapped in try/finally
- [x] [Review][Patch] Review Queue tab uses hardcoded path — fixed: added REVIEW_QUEUE to ROUTES constant
- [x] [Review][Patch] Unused `useAccount()` call in NavBar — fixed: removed unused import and call
- [x] [Review][Patch] `useEngineStatus` test calls hook as plain function — fixed: uses renderHook
- [x] [Review][Patch] `STATUS_TEXT` typed loosely — fixed: typed with `EngineStatus["mode"]`
- [x] [Review][Defer] `useAccount` query fires without auth gate (`enabled` flag) [useAccount.ts] — deferred, pre-existing architecture pattern
- [x] [Review][Defer] Dashboard layout flash of unauthenticated shell before redirect [layout.tsx] — deferred, pre-existing (middleware handles auth)
- [x] [Review][Defer] `useAccount` error state unhandled in consumers [WorkspaceIdentity.tsx] — deferred, broader error-handling concern
- [x] [Review][Defer] UserMenu shows "?" avatar before auth hydration completes [UserMenu.tsx] — deferred, pre-existing auth hydration timing
