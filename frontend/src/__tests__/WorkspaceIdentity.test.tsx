import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { WorkspaceIdentity } from "@/components/common/WorkspaceIdentity";

// Mock useAccount hook
vi.mock("@/hooks/useAccount", () => ({
  useAccount: vi.fn(),
}));

import { useAccount } from "@/hooks/useAccount";
const mockUseAccount = vi.mocked(useAccount);

describe("WorkspaceIdentity", () => {
  it("renders loading skeleton when loading", () => {
    mockUseAccount.mockReturnValue({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useAccount>);

    const { container } = render(<WorkspaceIdentity />);
    const pulseElements = container.querySelectorAll(".animate-pulse");
    expect(pulseElements.length).toBeGreaterThan(0);
  });

  it("renders SafeNet brand name and owner workspace", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        owner: { id: 1, email: "marc@example.com", first_name: "Marc", last_name: "B" },
        tier: "mid" as const,
        trial_ends_at: null,
        is_on_trial: false,
        stripe_connected: true,
        created_at: "2026-04-06T12:00:00Z",
      },
      isLoading: false,
    } as ReturnType<typeof useAccount>);

    render(<WorkspaceIdentity />);
    const safeNetElements = screen.getAllByText("SafeNet");
    expect(safeNetElements.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Marc B's workspace")).toBeInTheDocument();
  });

  it("renders 2-letter monogram from owner name", () => {
    mockUseAccount.mockReturnValue({
      data: {
        id: 1,
        owner: { id: 1, email: "marc@example.com", first_name: "Marc", last_name: "B" },
        tier: "mid" as const,
        trial_ends_at: null,
        is_on_trial: false,
        stripe_connected: true,
        created_at: "2026-04-06T12:00:00Z",
      },
      isLoading: false,
    } as ReturnType<typeof useAccount>);

    render(<WorkspaceIdentity />);
    expect(screen.getByText("MB")).toBeInTheDocument();
  });
});
