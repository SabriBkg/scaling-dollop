# Story 1.4: Next.js Frontend Skeleton, Design Token System & State Management

Status: done

## Story

As a developer,
I want the Next.js frontend initialized with SafeNet's design token system, shadcn/ui, and state management configured,
So that all subsequent UI stories build on a consistent, accessible, and theme-aware foundation.

## Acceptance Criteria

**AC1 — Directory structure:**
- **Given** the Next.js app is initialized with TypeScript, Tailwind, App Router, ESLint, and `src/` directory
- **When** I inspect `src/`
- **Then** it contains: `app/` (routes + layouts), `components/ui/` (shadcn/ui primitives — never hand-edited), `components/common/`, `components/dashboard/`, `hooks/`, `stores/`, `lib/`, `types/`

**AC2 — Design token system:**
- **Given** the global CSS file at `src/app/globals.css`
- **When** I inspect it
- **Then** all 13 semantic CSS custom properties are defined in both `:root` (light) and `.dark` (dark):
  `--bg-base`, `--bg-surface`, `--bg-elevated`, `--sn-border` (renamed from `--border` to avoid conflict with shadcn's own `--border` variable), `--text-primary`, `--text-secondary`, `--text-tertiary`, `--accent-recovery`, `--accent-active`, `--accent-fraud`, `--accent-neutral`, `--cta`, `--cta-hover`
- **And** the Tailwind config extends these as semantic utility aliases (border alias: `safenet-border` → `var(--sn-border)`)
- **And** Inter variable font is loaded with `font-variant-numeric: tabular-nums` applied to all monetary value display elements (UX-DR12)

**AC3 — shadcn/ui components:**
- **Given** shadcn/ui is initialized with the neutral theme
- **When** I check `components/ui/`
- **Then** the following are present: `Button`, `Badge`, `Card`, `Dialog`, `Sheet`, `Table`, `Checkbox`, `Sonner` (replaces `Toast` in shadcn v4 base-nova — `toast` component not available in this style), `Popover`, `Select`, `Avatar`, `Separator`, `Input`, `Textarea`, `NavigationMenu`

**AC4 — Axios API client:**
- **Given** a user makes an authenticated API request
- **When** the axios instance in `src/lib/api.ts` sends it
- **Then** the JWT access token is sent via httpOnly cookie (`safenet_access`) with `withCredentials: true`
- **And** a 401 response triggers a call to `/api/auth/refresh`, then retries the original request once
- **And** if refresh fails, the user is redirected to `/login`
- **Note:** The file is `src/lib/api.ts` (not `apiClient.ts`) — established in Story 1.1, all existing pages import from `api.ts`

**AC5 — TanStack Query v5 configured:**
- **Given** TanStack Query v5 is configured
- **When** I inspect the app root layout
- **Then** `QueryClientProvider` wraps the application with a 5-minute `staleTime` default for dashboard queries
- **And** no `useState` is used anywhere for server data

**AC6 — Zustand stores configured:**
- **Given** Zustand stores are configured
- **When** I inspect `src/stores/`
- **Then** `uiStore.ts` manages `activeSubscriberId`, `batchSelection`, and `themePreference`
- **And** `authStore.ts` manages JWT tokens and user identity

## Tasks / Subtasks

- [x] Task 1: Install shadcn/ui dependencies and run init (AC: 3)
  - [x] 1.1: Install peer dependencies: `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`
  - [x] 1.2: Run `npx shadcn@latest init` — choose: style=default, base-color=neutral, CSS variables=yes
  - [x] 1.3: Add all 15 required shadcn components via `npx shadcn@latest add button badge card dialog sheet table checkbox toast popover select avatar separator input textarea navigation-menu`
  - [x] 1.4: Remove `.gitkeep` from `src/components/ui/`, verify generated component files are present

- [x] Task 2: Implement SafeNet design token system in globals.css (AC: 2)
  - [x] 2.1: Add all 13 SafeNet CSS custom properties to `:root` (light values)
  - [x] 2.2: Add all 13 SafeNet CSS custom properties to `.dark` (dark values)
  - [x] 2.3: Load Inter variable font via `@next/font/google` or `next/font/google` in root layout
  - [x] 2.4: Add `.tabular-nums` utility — `font-variant-numeric: tabular-nums` — for monetary displays

- [x] Task 3: Update Tailwind config with semantic aliases (AC: 2)
  - [x] 3.1: Extend Tailwind `colors` with SafeNet token aliases mapping to CSS variables
  - [x] 3.2: Verify shadcn/ui init did not overwrite SafeNet token mappings

- [x] Task 4: Update root layout with Inter font and QueryClientProvider (AC: 5)
  - [x] 4.1: Create `src/app/providers.tsx` as `"use client"` wrapper with `QueryClientProvider` and 5-min `staleTime` default
  - [x] 4.2: Import `Providers` in `src/app/layout.tsx` and wrap `{children}`
  - [x] 4.3: Configure Inter variable font in `layout.tsx` using `next/font/google` and apply to `<html>` element

- [x] Task 5: Create Zustand stores (AC: 6)
  - [x] 5.1: Create `src/stores/uiStore.ts` with `activeSubscriberId`, `batchSelection` (Set), `themePreference`
  - [x] 5.2: Create `src/stores/authStore.ts` with JWT token state and user identity
  - [x] 5.3: Remove `.gitkeep` from `src/stores/`

- [x] Task 6: Update formatters.ts with monetary formatting using tabular-nums (AC: 2)
  - [x] 6.1: Enhance `formatCurrency` to use EUR by default and produce tabular-num-ready output
  - [x] 6.2: Add `formatRelativeTime` for "2m ago" / "next in 5m" patterns used in EngineStatusIndicator

- [x] Task 7: Run ESLint and verify no regressions (AC: all)
  - [x] 7.1: Run `npx eslint src/` — passes with 0 errors (migrated to ESLint 9 flat config)
  - [x] 7.2: Verify existing `src/app/(auth)/login/page.tsx`, `middleware.ts`, `api.ts` still compile without errors

## Dev Notes

### Current Codebase State (Critical — Read Before Implementing)

Story 1.1 established the frontend skeleton. The following already exists and **must not be broken**:

| File | Status | Note |
|------|--------|------|
| `src/app/globals.css` | Stub (Tailwind only) | Extend — do NOT replace |
| `src/app/layout.tsx` | Basic root layout | Extend with font + providers |
| `src/lib/api.ts` | ✅ Complete | Do NOT rename or duplicate as `apiClient.ts` |
| `src/lib/auth.ts` | ✅ Complete | `setTokens()` and `clearTokens()` via cookie bridge |
| `src/lib/constants.ts` | ✅ Complete | `API_URL`, `ROUTES` constants |
| `src/lib/formatters.ts` | Stub | Extend — comment says "Story 1.4 adds..." |
| `src/middleware.ts` | ✅ Complete | Reads `safenet_access` httpOnly cookie |
| `src/app/api/auth/login/route.ts` | ✅ Complete | Cookie bridge (sets httpOnly cookies) |
| `src/app/api/auth/refresh/route.ts` | ✅ Complete | Refresh handler |
| `src/types/account.ts` | ✅ Complete | `User`, `Account`, `StripeConnection`, `AuthTokens` types |
| `src/types/index.ts` | ✅ Complete | `ApiResponse<T>`, `ApiError` |
| `src/components/*/`  | `.gitkeep` placeholders | Remove `.gitkeep` when adding real files |
| `src/stores/` | `.gitkeep` placeholder | Remove when adding stores |

### AC4 File Naming Note

The story AC mentions `src/lib/apiClient.ts` but the file **is and will remain** `src/lib/api.ts`. This was established in Story 1.1. All existing pages import from `@/lib/api`. Do NOT create a separate `apiClient.ts` — it would duplicate the axios instance and create import confusion.

The existing `api.ts` already satisfies AC4:
- Uses `withCredentials: true` for automatic httpOnly cookie transmission
- Has 401 interceptor → calls `/api/auth/refresh` → retries → redirects to `/login` on failure

### shadcn/ui Installation (Task 1) — Critical Details

**This is NOT a regular npm package.** shadcn/ui CLI generates component files into your codebase.

```bash
# From frontend/ directory
cd frontend

# Step 1: Install peer deps (shadcn needs these)
npm install class-variance-authority clsx tailwind-merge lucide-react

# Step 2: Initialize shadcn/ui
# When prompted:
# - Style: Default
# - Base color: Neutral
# - Global CSS: src/app/globals.css
# - CSS variables: Yes
# - Tailwind config: tailwind.config.ts
# - Components alias: @/components
# - Utils alias: @/lib/utils
# - React Server Components: Yes
npx shadcn@latest init

# Step 3: Add all required components
npx shadcn@latest add button badge card dialog sheet table checkbox toast popover select avatar separator input textarea navigation-menu
```

**What shadcn init modifies:**
- `tailwind.config.ts` — adds shadcn CSS variable references (darkMode, animation)
- `src/app/globals.css` — adds shadcn's own CSS variables (`--background`, `--foreground`, etc.)
- Creates `src/lib/utils.ts` with `cn()` helper (clsx + tailwind-merge)

**Critical:** After shadcn init runs, you MUST ADD the SafeNet design tokens on top of whatever shadcn added to `globals.css`. Do NOT let shadcn overwrite the SafeNet tokens. Keep both systems.

**What shadcn add creates:**
Each component is created as a single `.tsx` file in `src/components/ui/`. Example: `button.tsx`, `badge.tsx`, etc. These files are yours — they live in the repo, not in node_modules.

### Design Token System (Task 2) — Exact Values

Add SafeNet tokens to `globals.css` alongside the shadcn variables:

```css
/* ============================================
   SafeNet Design Tokens
   Source: UX-DR12, UX specification
   ============================================ */

:root {
  /* Backgrounds */
  --bg-base: #F8F9FC;
  --bg-surface: #FFFFFF;
  --bg-elevated: #FFFFFF;

  /* Borders */
  --border: #E2E5EF;

  /* Text */
  --text-primary: #0F1117;
  --text-secondary: #4B5563;
  --text-tertiary: #9CA3AF;

  /* Status accents — UX-DR10 */
  --accent-recovery: #10B981;   /* green — Recovered status */
  --accent-active: #3B82F6;     /* blue — Active status */
  --accent-fraud: #EF4444;      /* red — Fraud Flagged status */
  --accent-neutral: #9CA3AF;    /* grey — Passive Churn status */

  /* CTA */
  --cta: #3B82F6;
  --cta-hover: #2563EB;
}

.dark {
  /* Backgrounds */
  --bg-base: #0F1117;
  --bg-surface: #1A1D27;
  --bg-elevated: #242736;

  /* Borders */
  --border: #2D3148;

  /* Text */
  --text-primary: #F9FAFB;
  --text-secondary: #9CA3AF;
  --text-tertiary: #6B7280;

  /* Status accents */
  --accent-recovery: #10B981;
  --accent-active: #60A5FA;
  --accent-fraud: #F87171;
  --accent-neutral: #6B7280;

  /* CTA */
  --cta: #60A5FA;
  --cta-hover: #3B82F6;
}

/* Tabular numbers for monetary values — UX-DR12 */
.tabular-nums {
  font-variant-numeric: tabular-nums;
}
```

**Note on #E2E5EF:** This exact color appears in UX spec: "CSS Grid with 1px hairline dividers on `#E2E5EF` background" — use it as `--border`.

### Tailwind Config Semantic Aliases (Task 3)

After shadcn init, update `tailwind.config.ts` to ADD SafeNet aliases. Do not replace the shadcn config:

```typescript
theme: {
  extend: {
    colors: {
      // SafeNet semantic color aliases — map to CSS custom properties
      'bg-base': 'var(--bg-base)',
      'bg-surface': 'var(--bg-surface)',
      'bg-elevated': 'var(--bg-elevated)',
      'safenet-border': 'var(--border)',
      'text-primary': 'var(--text-primary)',
      'text-secondary': 'var(--text-secondary)',
      'text-tertiary': 'var(--text-tertiary)',
      'accent-recovery': 'var(--accent-recovery)',
      'accent-active': 'var(--accent-active)',
      'accent-fraud': 'var(--accent-fraud)',
      'accent-neutral': 'var(--accent-neutral)',
      'cta': 'var(--cta)',
      'cta-hover': 'var(--cta-hover)',
    },
    // shadcn init may have added animations here — keep them
  },
},
```

Usage in components: `className="bg-bg-base text-text-primary border-safenet-border"`

### Root Layout + QueryClientProvider (Task 4)

**Problem:** `QueryClientProvider` requires `"use client"` but `layout.tsx` should remain a Server Component. Solution: extract a `Providers` client component.

```typescript
// src/app/providers.tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60 * 1000, // 5 minutes — architecture spec
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

```typescript
// src/app/layout.tsx — updated
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SafeNet",
  description: "Automated payment failure recovery",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

Then in `tailwind.config.ts`, add the font family:
```typescript
fontFamily: {
  sans: ["var(--font-inter)", "system-ui", "sans-serif"],
},
```

### Zustand Stores (Task 5)

**Architecture rule:** Zustand = UI-only client state. Never server data.

```typescript
// src/stores/uiStore.ts
import { create } from "zustand";

interface UIState {
  // Subscriber detail sheet
  activeSubscriberId: string | null;
  setActiveSubscriberId: (id: string | null) => void;

  // Batch selection for Supervised mode (FR14, UX-DR8)
  batchSelection: Set<string>;
  addToBatch: (id: string) => void;
  removeFromBatch: (id: string) => void;
  clearBatch: () => void;

  // Theme
  themePreference: "light" | "dark" | "system";
  setThemePreference: (theme: "light" | "dark" | "system") => void;
}

export const useUIStore = create<UIState>((set) => ({
  activeSubscriberId: null,
  setActiveSubscriberId: (id) => set({ activeSubscriberId: id }),

  batchSelection: new Set(),
  addToBatch: (id) =>
    set((state) => ({ batchSelection: new Set([...state.batchSelection, id]) })),
  removeFromBatch: (id) =>
    set((state) => {
      const next = new Set(state.batchSelection);
      next.delete(id);
      return { batchSelection: next };
    }),
  clearBatch: () => set({ batchSelection: new Set() }),

  themePreference: "system",
  setThemePreference: (theme) => set({ themePreference: theme }),
}));
```

```typescript
// src/stores/authStore.ts
import { create } from "zustand";
import type { User } from "@/types";

interface AuthState {
  // Note: actual tokens live in httpOnly cookies (XSS-safe).
  // authStore tracks identity only — NOT raw token strings.
  user: User | null;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  setUser: (user) => set({ user, isAuthenticated: user !== null }),
  clearAuth: () => set({ user: null, isAuthenticated: false }),
}));
```

**Important:** `authStore` does NOT store JWT token strings. Tokens are in httpOnly cookies (managed by `src/lib/auth.ts`). The store tracks user identity for UI purposes only.

### Formatters Update (Task 6)

Extend the existing `src/lib/formatters.ts` stub:

```typescript
// Add to existing formatters.ts
export const formatRelativeTime = (date: string | Date): string => {
  const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
};

export const formatTimeUntil = (date: string | Date): string => {
  const seconds = Math.floor((new Date(date).getTime() - Date.now()) / 1000);
  if (seconds < 60) return "< 1m";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
};
```

For monetary values, the existing `formatCurrency` uses `Intl.NumberFormat` — it already produces tabular-number-ready output. Use the `.tabular-nums` CSS class from globals.css on the wrapping element.

### Architecture Compliance Rules

**All AI agents MUST follow (from architecture.md):**
- TypeScript fields mirroring API: use `snake_case` (e.g., `subscriber_status`, not `subscriberStatus`)
- No `useState` for server data — TanStack Query only
- TypeScript component files: `PascalCase.tsx`
- Hook files: `useCamelCase.ts`
- Store files: `camelCaseStore.ts` → actual files are `uiStore.ts`, `authStore.ts`
- `@/*` alias maps to `./src/*` (tsconfig paths already configured)
- All monetary amounts from API are `integer cents` — only format in display layer

**Anti-patterns to avoid:**
- Do NOT use `useState` for data that comes from the API
- Do NOT store JWT token strings in Zustand (use httpOnly cookies via `src/lib/auth.ts`)
- Do NOT hand-edit files in `src/components/ui/` (these are shadcn-generated)
- Do NOT create `src/lib/apiClient.ts` — it already exists as `src/lib/api.ts`

### Testing Requirements

This story has no backend — ESLint + TypeScript compilation are the test suite.

```bash
# From frontend/ directory
npm run lint         # Must pass with 0 errors
npx tsc --noEmit     # Must pass — catches type errors in new files
```

Check specifically:
- `uiStore.ts` and `authStore.ts` correctly typed (no `any`)
- `providers.tsx` imports are correct
- `layout.tsx` Inter font applied correctly
- `globals.css` CSS variables syntax is valid

### Project Structure Notes

**After this story, `src/` should contain:**
```
src/
  app/
    (auth)/login/page.tsx         ← existing stub
    (auth)/register/page.tsx      ← existing stub
    (dashboard)/layout.tsx        ← existing stub
    api/auth/login/route.ts       ← existing ✅
    api/auth/refresh/route.ts     ← existing ✅
    globals.css                   ← MODIFIED (design tokens added)
    layout.tsx                    ← MODIFIED (Inter font + Providers)
    page.tsx                      ← existing
    providers.tsx                 ← NEW (QueryClientProvider)
  components/
    ui/                           ← shadcn generated (15 components)
    common/                       ← still empty (Story 2.x)
    dashboard/                    ← still empty (Story 2.x)
    settings/                     ← still empty (Story 3.x)
    subscriber/                   ← still empty (Story 5.x)
  hooks/                          ← still empty (Story 2.x)
  lib/
    api.ts                        ← existing ✅ (do NOT rename)
    auth.ts                       ← existing ✅
    constants.ts                  ← existing ✅
    formatters.ts                 ← MODIFIED (add formatRelativeTime, formatTimeUntil)
    utils.ts                      ← NEW (generated by shadcn — cn() helper)
  middleware.ts                   ← existing ✅
  stores/
    uiStore.ts                    ← NEW
    authStore.ts                  ← NEW
  types/
    account.ts                    ← existing ✅
    index.ts                      ← existing ✅
```

### References

- Design tokens: [Source: _bmad-output/epics.md#Story 1.4 AC2] and [Source: _bmad-output/ux-design-specification.md#UX-DR12]
- shadcn/ui Badge variants: [Source: _bmad-output/epics.md#UX-DR10] — `Recovered (green/--accent-recovery)`, `Active (blue/--accent-active)`, `Fraud Flagged (red/--accent-fraud)`, `Passive Churn (grey/--accent-neutral)`
- Frontend architecture: [Source: _bmad-output/architecture.md#Frontend Architecture]
- Naming conventions: [Source: _bmad-output/architecture.md#Naming Patterns]
- Anti-patterns: [Source: _bmad-output/architecture.md#Enforcement Guidelines]
- Cookie-based auth rationale: [Source: frontend/src/app/api/auth/login/route.ts]
- TanStack Query pattern: [Source: _bmad-output/architecture.md#Communication Patterns]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

- shadcn v4 uses `sonner` instead of `toast` component — `toast` not found in base-nova registry
- ESLint 9 requires flat config (`eslint.config.mjs`) — `next lint` removed in Next.js 16
- shadcn init added Geist font to layout.tsx — replaced with Inter per spec
- Used `--sn-border` CSS variable to avoid conflict with shadcn's `--border`

### Completion Notes List

- Task 1: Installed shadcn/ui v4 with base-nova style, neutral base color, CSS variables. All 15 components generated (sonner replaces toast in v4). Peer deps installed: class-variance-authority, clsx, tailwind-merge, lucide-react.
- Task 2: Added all 13 SafeNet design tokens to globals.css in both :root (light) and .dark (dark) modes, alongside shadcn's own CSS variables. Added .tabular-nums utility class.
- Task 3: Extended tailwind.config.ts with SafeNet semantic color aliases mapping to CSS custom properties. Added Inter font family config.
- Task 4: Created providers.tsx with QueryClientProvider (5-min staleTime). Updated layout.tsx with Inter variable font and Providers wrapper.
- Task 5: Created uiStore.ts (activeSubscriberId, batchSelection Set, themePreference) and authStore.ts (user identity only — tokens in httpOnly cookies). Removed .gitkeep files.
- Task 6: Updated formatCurrency default to EUR. Added formatRelativeTime and formatTimeUntil utilities.
- Task 7: Migrated to ESLint 9 flat config. All lint and TypeScript type-checks pass with 0 errors. Existing pages unaffected.

### File List

- `_bmad-output/1-4-next-js-frontend-skeleton-design-token-system-state-management.md` (this file)
- `frontend/package.json` (modified — added shadcn deps, updated lint script, eslint v9)
- `frontend/package-lock.json` (modified — regenerated)
- `frontend/components.json` (new — shadcn config)
- `frontend/eslint.config.mjs` (new — ESLint 9 flat config, replaces .eslintrc.json)
- `frontend/.eslintrc.json` (deleted — replaced by flat config)
- `frontend/src/app/globals.css` (modified — shadcn CSS + SafeNet design tokens)
- `frontend/src/app/layout.tsx` (modified — Inter font + Providers wrapper)
- `frontend/src/app/providers.tsx` (new — QueryClientProvider)
- `frontend/src/lib/utils.ts` (new — shadcn cn() helper)
- `frontend/src/lib/formatters.ts` (modified — EUR default, formatRelativeTime, formatTimeUntil)
- `frontend/src/stores/uiStore.ts` (new)
- `frontend/src/stores/authStore.ts` (new)
- `frontend/src/stores/.gitkeep` (deleted)
- `frontend/src/components/ui/.gitkeep` (deleted)
- `frontend/src/components/ui/button.tsx` (new — shadcn)
- `frontend/src/components/ui/badge.tsx` (new — shadcn)
- `frontend/src/components/ui/card.tsx` (new — shadcn)
- `frontend/src/components/ui/dialog.tsx` (new — shadcn)
- `frontend/src/components/ui/sheet.tsx` (new — shadcn)
- `frontend/src/components/ui/table.tsx` (new — shadcn)
- `frontend/src/components/ui/checkbox.tsx` (new — shadcn)
- `frontend/src/components/ui/sonner.tsx` (new — shadcn toast replacement)
- `frontend/src/components/ui/popover.tsx` (new — shadcn)
- `frontend/src/components/ui/select.tsx` (new — shadcn)
- `frontend/src/components/ui/avatar.tsx` (new — shadcn)
- `frontend/src/components/ui/separator.tsx` (new — shadcn)
- `frontend/src/components/ui/input.tsx` (new — shadcn)
- `frontend/src/components/ui/textarea.tsx` (new — shadcn)
- `frontend/src/components/ui/navigation-menu.tsx` (new — shadcn)
- `frontend/tailwind.config.ts` (modified — SafeNet color aliases + Inter font family)

### Review Findings

- [x] [Review][Decision] D1: `--sn-border` used instead of AC2-specified `--border` — accepted deviation; AC2 amended to reflect `--sn-border` / `safenet-border` naming
- [x] [Review][Decision] D2: `Toast` listed in AC3 but `sonner` component shipped — accepted; AC3 amended to reflect `Sonner` as shadcn v4 replacement
- [x] [Review][Decision] D3: `formatCurrency` default changed from `USD` to `EUR` — reverted to `USD`; currency must be passed explicitly at call sites for EUR formatting [`frontend/src/lib/formatters.ts`]
- [x] [Review][Decision] D4: Dark mode stack incomplete — fixed: added `darkMode: 'class'` to `tailwind.config.ts`; added `ThemeProvider` from `next-themes` to `providers.tsx`
- [x] [Review][Decision] D5: `components/common/` and `components/dashboard/` not git-tracked — fixed: added `.gitkeep` files
- [x] [Review][Patch] P1: `formatRelativeTime` returns `"just now"` for future dates; no day-level display for durations >24h — fixed: added `seconds < 0` guard returns "just now"; added day fallback [`frontend/src/lib/formatters.ts`]
- [x] [Review][Patch] P2: `formatTimeUntil` returns `"< 1m"` for past dates — fixed: added `seconds <= 0` guard returns `"overdue"` [`frontend/src/lib/formatters.ts`]
- [x] [Review][Patch] P3: CSS variable self-reference no-op: `.theme { --font-sans: var(--font-sans) }` — fixed: changed to `var(--font-inter)`, removed self-ref [`frontend/src/app/globals.css`]
- [x] [Review][Patch] P4: `globals.css` missing newline at end of file — fixed [`frontend/src/app/globals.css`]
- [x] [Review][Patch] P5: `shadcn` listed under `dependencies` — fixed: moved to `devDependencies` [`frontend/package.json`]
- [x] [Review][Defer] W1: `batchSelection: Set<string>` not JSON-serializable — will silently corrupt if Zustand persist middleware is added later [`frontend/src/stores/uiStore.ts`] — deferred, pre-existing
- [x] [Review][Defer] W2: `authStore` has no Zustand persistence — intentional design (tokens in httpOnly cookies, middleware handles auth gate) [`frontend/src/stores/authStore.ts`] — deferred, pre-existing
- [x] [Review][Defer] W3: `QueryClient` SSR hydration boundary undocumented — safe pattern but server prefetch state is not bridged to client [`frontend/src/app/providers.tsx`] — deferred, pre-existing

### Change Log

- 2026-04-10: Story created by create-story workflow
- 2026-04-10: Story implementation completed — all 7 tasks done, all ACs satisfied
- 2026-04-10: Code review completed — 5 decision-needed, 5 patch, 3 deferred, 5 dismissed
