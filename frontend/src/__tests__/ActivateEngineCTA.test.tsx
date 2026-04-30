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

  it("renders the DPA-sign CTA for mid-tier accounts without DPA", () => {
    // v1: the only activation step is DPA acceptance — there is no
    // "select recovery mode" step. Unsigned Mid users see a Sign CTA.
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
    expect(
      screen.getByText("Sign the Data Processing Agreement"),
    ).toBeInTheDocument();
  });

  it("does not render for mid-tier accounts that have already signed the DPA", () => {
    // v1: once DPA is signed there is no further activation step. Rendering
    // a "Select recovery mode" CTA would link to the /activate/mode redirect
    // stub and bounce the user back to the dashboard in a loop.
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        dpa_accepted: true,
        engine_active: false,
      },
      isLoading: false,
    });

    const { container } = render(<ActivateEngineCTA />, { wrapper: createWrapper() });
    expect(container.innerHTML).toBe("");
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
