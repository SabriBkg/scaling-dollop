import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ToneSelector } from "@/components/settings/ToneSelector";
import type { Account } from "@/types";

const mockPost = vi.fn();
const mockSuccess = vi.fn();
const mockError = vi.fn();

vi.mock("@/lib/api", () => ({
  default: { post: (...args: unknown[]) => mockPost(...args) },
}));

vi.mock("sonner", () => ({
  toast: {
    success: (msg: string) => mockSuccess(msg),
    error: (msg: string) => mockError(msg),
  },
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

const baseAccount: Account = {
  id: 1,
  owner: { id: 1, email: "owner@example.com", first_name: "A", last_name: "B" },
  company_name: "Acme",
  tier: "mid",
  trial_ends_at: null,
  is_on_trial: false,
  trial_days_remaining: null,
  next_scan_at: null,
  engine_active: true,
  stripe_connected: true,
  profile_complete: true,
  dpa_accepted: true,
  dpa_accepted_at: "2026-01-01T00:00:00Z",
  engine_mode: "autopilot",
  notification_tone: "professional",
  created_at: "2026-01-01T00:00:00Z",
};

describe("ToneSelector", () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockSuccess.mockReset();
    mockError.mockReset();
  });

  it("renders three tone options", () => {
    render(
      <ToneSelector account={baseAccount} value="professional" onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );

    expect(screen.getByText("Professional")).toBeInTheDocument();
    expect(screen.getByText("Friendly")).toBeInTheDocument();
    expect(screen.getByText("Minimal")).toBeInTheDocument();

    const radios = screen.getAllByRole("radio");
    expect(radios).toHaveLength(3);
  });

  it("marks the current value as checked", () => {
    render(
      <ToneSelector account={baseAccount} value="friendly" onChange={vi.fn()} />,
      { wrapper: createWrapper() },
    );

    expect(screen.getByDisplayValue("friendly")).toBeChecked();
    expect(screen.getByDisplayValue("professional")).not.toBeChecked();
    expect(screen.getByDisplayValue("minimal")).not.toBeChecked();
  });

  it("calls onChange and posts to API on selection", async () => {
    mockPost.mockResolvedValue({ data: { data: { ...baseAccount, notification_tone: "minimal" } } });
    const onChange = vi.fn();

    render(
      <ToneSelector account={baseAccount} value="professional" onChange={onChange} />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByDisplayValue("minimal"));

    expect(onChange).toHaveBeenCalledWith("minimal");
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/account/notification-tone/", { tone: "minimal" });
    });
    await waitFor(() => {
      expect(mockSuccess).toHaveBeenCalled();
    });
  });

  it("rolls back optimistic update on API failure", async () => {
    mockPost.mockRejectedValue(new Error("server"));
    const onChange = vi.fn();

    render(
      <ToneSelector account={baseAccount} value="professional" onChange={onChange} />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByDisplayValue("friendly"));

    await waitFor(() => {
      expect(mockError).toHaveBeenCalled();
    });
    // First call applied optimistic, second call rolled back to "professional"
    expect(onChange).toHaveBeenNthCalledWith(1, "friendly");
    expect(onChange).toHaveBeenNthCalledWith(2, "professional");
  });

  it("disables all radios and shows hint when disabled", () => {
    render(
      <ToneSelector
        account={baseAccount}
        value="professional"
        onChange={vi.fn()}
        disabled
        disabledHint="Upgrade to enable tone selection."
      />,
      { wrapper: createWrapper() },
    );

    expect(screen.getByText("Upgrade to enable tone selection.")).toBeInTheDocument();
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio).toBeDisabled();
    }
  });

  it("does not POST when clicking the already-selected tone", async () => {
    const onChange = vi.fn();

    render(
      <ToneSelector account={baseAccount} value="friendly" onChange={onChange} />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByDisplayValue("friendly"));

    expect(onChange).not.toHaveBeenCalled();
    expect(mockPost).not.toHaveBeenCalled();
  });
});
