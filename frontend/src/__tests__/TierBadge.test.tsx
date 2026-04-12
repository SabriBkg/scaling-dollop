import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TierBadge } from "@/components/settings/TierBadge";
import type { Account } from "@/types";

function makeAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: 1,
    owner: { id: 1, email: "test@example.com", first_name: "Test", last_name: "User" },
    company_name: "TestCo",
    tier: "mid",
    trial_ends_at: null,
    is_on_trial: false,
    trial_days_remaining: null,
    next_scan_at: null,
    engine_active: true,
    stripe_connected: true,
    profile_complete: true,
    created_at: "2026-04-06T12:00:00Z",
    ...overrides,
  };
}

describe("TierBadge", () => {
  it("renders Free badge for free tier", () => {
    render(<TierBadge account={makeAccount({ tier: "free", engine_active: false })} />);
    expect(screen.getByText("Free")).toBeInTheDocument();
  });

  it("renders Mid badge for paid mid", () => {
    render(<TierBadge account={makeAccount({ tier: "mid" })} />);
    expect(screen.getByText("Mid")).toBeInTheDocument();
  });

  it("renders trial badge with days remaining", () => {
    render(
      <TierBadge
        account={makeAccount({
          tier: "mid",
          is_on_trial: true,
          trial_days_remaining: 15,
        })}
      />
    );
    expect(screen.getByText("Mid — Trial (15d left)")).toBeInTheDocument();
  });

  it("renders Pro badge", () => {
    render(<TierBadge account={makeAccount({ tier: "pro" })} />);
    expect(screen.getByText("Pro")).toBeInTheDocument();
  });
});
