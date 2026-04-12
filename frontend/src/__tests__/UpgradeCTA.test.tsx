import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UpgradeCTA } from "@/components/dashboard/UpgradeCTA";

const mockUseAccount = vi.fn();

vi.mock("@/hooks/useAccount", () => ({
  useAccount: () => mockUseAccount(),
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

describe("UpgradeCTA", () => {
  beforeEach(() => {
    mockUseAccount.mockReset();
  });

  it("renders CTA button for free-tier accounts", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "free",
        is_on_trial: false,
        stripe_connected: true,
        created_at: "2026-04-06T12:00:00Z",
      },
      isLoading: false,
    });

    render(<UpgradeCTA />, { wrapper: createWrapper() });
    expect(screen.getByRole("button")).toBeInTheDocument();
    expect(screen.getByRole("button").textContent).toContain(
      "Activate recovery engine"
    );
    expect(screen.getByRole("button").textContent).toContain("29/month");
  });

  it("does not render for mid-tier accounts", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        is_on_trial: false,
        stripe_connected: true,
        created_at: "2026-04-06T12:00:00Z",
      },
      isLoading: false,
    });

    const { container } = render(<UpgradeCTA />, { wrapper: createWrapper() });
    expect(container.innerHTML).toBe("");
  });

  it("does not render when account is loading", () => {
    mockUseAccount.mockReturnValue({
      data: null,
      isLoading: true,
    });

    const { container } = render(<UpgradeCTA />, { wrapper: createWrapper() });
    expect(container.innerHTML).toBe("");
  });
});
