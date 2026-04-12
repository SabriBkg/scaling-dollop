import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextScanCountdown } from "@/components/dashboard/NextScanCountdown";

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

describe("NextScanCountdown", () => {
  beforeEach(() => {
    mockUseAccount.mockReset();
  });

  it("renders countdown for free-tier with next_scan_at", () => {
    const futureDate = new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString();
    mockUseAccount.mockReturnValue({
      data: { tier: "free", next_scan_at: futureDate },
      isLoading: false,
    });

    render(<NextScanCountdown />, { wrapper: createWrapper() });
    expect(screen.getByText(/Your next scan is in/)).toBeInTheDocument();
  });

  it("does not render for mid-tier", () => {
    mockUseAccount.mockReturnValue({
      data: { tier: "mid", next_scan_at: null },
      isLoading: false,
    });

    const { container } = render(<NextScanCountdown />, { wrapper: createWrapper() });
    expect(container.innerHTML).toBe("");
  });

  it("does not render when no next_scan_at", () => {
    mockUseAccount.mockReturnValue({
      data: { tier: "free", next_scan_at: null },
      isLoading: false,
    });

    const { container } = render(<NextScanCountdown />, { wrapper: createWrapper() });
    expect(container.innerHTML).toBe("");
  });
});
