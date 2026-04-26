import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SettingsPage from "@/app/(dashboard)/settings/page";

const mockUseAccount = vi.fn();

vi.mock("@/hooks/useAccount", () => ({
  useAccount: () => mockUseAccount(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/hooks/useNotificationPreview", () => ({
  useNotificationPreview: () => ({
    data: {
      tone: "professional",
      subject: "Sample subject",
      html_body: "<p>preview</p>",
      sample_subscriber_email: "subscriber@example.com",
      sample_decline_code: "card_expired",
    },
    isLoading: false,
    isError: false,
  }),
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

describe("SettingsPage - Mode Switcher", () => {
  beforeEach(() => {
    mockUseAccount.mockReset();
  });

  it("shows Recovery Mode section when DPA accepted", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        is_on_trial: false,
        dpa_accepted: true,
        engine_mode: "autopilot",
        trial_days_remaining: null,
        stripe_connected: true,
      },
      isLoading: false,
    });

    render(<SettingsPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Recovery Mode")).toBeInTheDocument();

    const engineRadios = screen
      .getAllByRole("radio")
      .filter((r) => r.getAttribute("name") === "engine_mode");
    expect(engineRadios).toHaveLength(2);

    const autopilotRadio = screen.getByDisplayValue("autopilot");
    expect(autopilotRadio).toBeChecked();
  });

  it("hides Recovery Mode section when DPA not accepted", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        is_on_trial: false,
        dpa_accepted: false,
        engine_mode: null,
        trial_days_remaining: null,
        stripe_connected: true,
      },
      isLoading: false,
    });

    render(<SettingsPage />, { wrapper: createWrapper() });
    expect(screen.queryByText("Recovery Mode")).not.toBeInTheDocument();
  });

  it("shows supervised as selected when that is the current mode", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        tier: "mid",
        is_on_trial: false,
        dpa_accepted: true,
        engine_mode: "supervised",
        trial_days_remaining: null,
        stripe_connected: true,
      },
      isLoading: false,
    });

    render(<SettingsPage />, { wrapper: createWrapper() });
    const supervisedRadio = screen.getByDisplayValue("supervised");
    expect(supervisedRadio).toBeChecked();
  });
});
