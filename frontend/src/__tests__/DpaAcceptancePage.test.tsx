import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DpaAcceptancePage from "@/app/(dashboard)/activate/page";

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

describe("DpaAcceptancePage", () => {
  beforeEach(() => {
    mockUseAccount.mockReset();
    mockPush.mockReset();
    mockReplace.mockReset();
  });

  it("renders DPA content sections", () => {
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

    render(<DpaAcceptancePage />, { wrapper: createWrapper() });

    expect(screen.getByText("Data Processing Agreement")).toBeInTheDocument();
    expect(screen.getByText("What SafeNet Processes")).toBeInTheDocument();
    expect(screen.getByText("On Whose Behalf")).toBeInTheDocument();
    expect(screen.getByText("Purpose of Processing")).toBeInTheDocument();
    expect(screen.getByText("Retention Policy")).toBeInTheDocument();
    expect(screen.getByText("Security Measures")).toBeInTheDocument();
    expect(screen.getByText("I accept and sign")).toBeInTheDocument();
  });

  it("shows loading spinner while account is loading", () => {
    mockUseAccount.mockReturnValue({
      data: null,
      isLoading: true,
    });

    const { container } = render(<DpaAcceptancePage />, { wrapper: createWrapper() });
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("redirects to /dashboard if DPA already accepted", () => {
    // v1: post-accept lands on the failed-payments dashboard, not /activate/mode.
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        dpa_accepted: true,
        dpa_accepted_at: "2026-04-14T00:00:00Z",
        dpa_version: "v1.0-2026-04-29",
        engine_mode: null,
        company_name: "TestCo",
      },
      isLoading: false,
    });

    render(<DpaAcceptancePage />, { wrapper: createWrapper() });
    expect(mockReplace).toHaveBeenCalledWith("/dashboard");
  });

  it("has a go back link", () => {
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

    render(<DpaAcceptancePage />, { wrapper: createWrapper() });
    expect(screen.getByText("Go back to dashboard")).toBeInTheDocument();
  });
});
