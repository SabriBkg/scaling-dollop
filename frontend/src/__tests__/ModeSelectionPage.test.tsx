import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ModeSelectionPage from "@/app/(dashboard)/activate/mode/page";

const mockUseAccount = vi.fn();
const mockPush = vi.fn();
const mockReplace = vi.fn();

vi.mock("@/hooks/useAccount", () => ({
  useAccount: () => mockUseAccount(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("ModeSelectionPage", () => {
  beforeEach(() => {
    mockUseAccount.mockReset();
    mockPush.mockReset();
    mockReplace.mockReset();
  });

  it("renders both mode options", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        dpa_accepted: true,
        dpa_accepted_at: "2026-04-14T00:00:00Z",
        engine_mode: null,
        company_name: "TestCo",
      },
      isLoading: false,
    });

    render(<ModeSelectionPage />, { wrapper: createWrapper() });

    expect(screen.getByText("Autopilot")).toBeInTheDocument();
    expect(screen.getByText("Supervised")).toBeInTheDocument();
    expect(
      screen.getByText(
        "SafeNet handles all recovery automatically — no action required from you."
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "SafeNet queues actions for your review before executing."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Confirm and activate")).toBeInTheDocument();
  });

  it("shows loading spinner while account is loading", () => {
    mockUseAccount.mockReturnValue({
      data: null,
      isLoading: true,
    });

    const { container } = render(<ModeSelectionPage />, { wrapper: createWrapper() });
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("redirects to /activate if DPA not accepted", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        dpa_accepted: false,
        dpa_accepted_at: null,
        engine_mode: null,
        company_name: "TestCo",
      },
      isLoading: false,
    });

    render(<ModeSelectionPage />, { wrapper: createWrapper() });
    expect(mockReplace).toHaveBeenCalledWith("/activate");
  });

  it("redirects to dashboard if engine already active", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        dpa_accepted: true,
        dpa_accepted_at: "2026-04-14T00:00:00Z",
        engine_mode: "autopilot",
        company_name: "TestCo",
      },
      isLoading: false,
    });

    render(<ModeSelectionPage />, { wrapper: createWrapper() });
    expect(mockReplace).toHaveBeenCalledWith("/dashboard");
  });

  it("confirm button is disabled when no mode selected", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        dpa_accepted: true,
        dpa_accepted_at: "2026-04-14T00:00:00Z",
        engine_mode: null,
        company_name: "TestCo",
      },
      isLoading: false,
    });

    render(<ModeSelectionPage />, { wrapper: createWrapper() });
    const btn = screen.getByText("Confirm and activate");
    expect(btn).toBeDisabled();
  });
});
