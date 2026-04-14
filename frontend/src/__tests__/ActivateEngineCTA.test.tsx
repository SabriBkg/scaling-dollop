import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ActivateEngineCTA } from "@/components/dashboard/ActivateEngineCTA";

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

describe("ActivateEngineCTA", () => {
  beforeEach(() => {
    mockUseAccount.mockReset();
  });

  it("renders for mid-tier accounts without DPA", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        dpa_accepted: false,
        engine_active: false,
      },
      isLoading: false,
    });

    render(<ActivateEngineCTA />, { wrapper: createWrapper() });
    expect(screen.getByText("Activate recovery engine")).toBeInTheDocument();
  });

  it("renders for mid-tier accounts with DPA but no mode selected", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        dpa_accepted: true,
        engine_active: false,
      },
      isLoading: false,
    });

    render(<ActivateEngineCTA />, { wrapper: createWrapper() });
    expect(screen.getByText("Select recovery mode")).toBeInTheDocument();
  });

  it("does not render for free-tier accounts", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "free",
        dpa_accepted: false,
        engine_active: false,
      },
      isLoading: false,
    });

    const { container } = render(<ActivateEngineCTA />, { wrapper: createWrapper() });
    expect(container.innerHTML).toBe("");
  });

  it("does not render when engine is active", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        dpa_accepted: true,
        engine_active: true,
      },
      isLoading: false,
    });

    const { container } = render(<ActivateEngineCTA />, { wrapper: createWrapper() });
    expect(container.innerHTML).toBe("");
  });

  it("does not render when account is loading", () => {
    mockUseAccount.mockReturnValue({
      data: null,
      isLoading: true,
    });

    const { container } = render(<ActivateEngineCTA />, { wrapper: createWrapper() });
    expect(container.innerHTML).toBe("");
  });
});
