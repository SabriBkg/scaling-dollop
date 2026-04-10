import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NavBar } from "@/components/common/NavBar";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock useAccount
vi.mock("@/hooks/useAccount", () => ({
  useAccount: () => ({
    data: {
      id: 1,
      owner: { id: 1, email: "marc@test.com", first_name: "Marc", last_name: "B" },
      tier: "mid",
      trial_ends_at: null,
      is_on_trial: false,
      stripe_connected: true,
      created_at: "2026-04-06T12:00:00Z",
    },
    isLoading: false,
  }),
}));

// Mock useEngineStatus
vi.mock("@/hooks/useEngineStatus", () => ({
  useEngineStatus: () => ({
    mode: "paused",
    last_scan_at: null,
    next_scan_at: null,
  }),
}));

// Mock next-themes
vi.mock("next-themes", () => ({
  useTheme: () => ({
    resolvedTheme: "light",
    setTheme: vi.fn(),
  }),
}));

// Mock uiStore
vi.mock("@/stores/uiStore", () => ({
  useUIStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ setThemePreference: vi.fn() }),
}));

// Mock authStore
vi.mock("@/stores/authStore", () => ({
  useAuthStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ user: { first_name: "Marc", last_name: "B", email: "marc@test.com" }, clearAuth: vi.fn() }),
}));

describe("NavBar", () => {
  it("renders Dashboard and Settings navigation tabs", () => {
    render(<NavBar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders WorkspaceIdentity with SafeNet brand", () => {
    render(<NavBar />);
    const safeNetElements = screen.getAllByText("SafeNet");
    expect(safeNetElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders the header element with correct height class", () => {
    const { container } = render(<NavBar />);
    const header = container.querySelector("header");
    expect(header?.className).toContain("h-12");
  });

  it("highlights active tab with font-semibold", () => {
    render(<NavBar />);
    const dashboardLink = screen.getByText("Dashboard");
    expect(dashboardLink.className).toContain("font-semibold");
  });
});
