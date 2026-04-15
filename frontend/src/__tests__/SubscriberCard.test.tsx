import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SubscriberCard } from "@/components/dashboard/SubscriberCard";
import type { SubscriberCard as SubscriberCardType } from "@/types/subscriber";

function makeSubscriber(overrides: Partial<SubscriberCardType> = {}): SubscriberCardType {
  return {
    id: 1,
    stripe_customer_id: "cus_test123",
    email: "alice@example.com",
    status: "active",
    decline_code: "insufficient_funds",
    decline_reason: "Insufficient funds",
    amount_cents: 5000,
    needs_attention: false,
    excluded_from_automation: false,
    ...overrides,
  };
}

describe("SubscriberCard", () => {
  it("renders subscriber name and amount", () => {
    render(<SubscriberCard subscriber={makeSubscriber()} />);
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("$50.00")).toBeInTheDocument();
  });

  it("renders decline reason", () => {
    render(<SubscriberCard subscriber={makeSubscriber()} />);
    expect(screen.getByText("Insufficient funds")).toBeInTheDocument();
  });

  it("renders status badge for active", () => {
    render(<SubscriberCard subscriber={makeSubscriber({ status: "active" })} />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders status badge for recovered with green amount", () => {
    render(<SubscriberCard subscriber={makeSubscriber({ status: "recovered" })} />);
    expect(screen.getByText("Recovered")).toBeInTheDocument();
  });

  it("renders status badge for fraud_flagged", () => {
    render(
      <SubscriberCard
        subscriber={makeSubscriber({ status: "fraud_flagged", needs_attention: true })}
      />
    );
    expect(screen.getByText("Fraud Flagged")).toBeInTheDocument();
  });

  it("renders status badge for passive_churn", () => {
    render(<SubscriberCard subscriber={makeSubscriber({ status: "passive_churn" })} />);
    expect(screen.getByText("Passive Churn")).toBeInTheDocument();
  });

  it("renders fraud flagged label and amber border for fraud cards", () => {
    const { container } = render(
      <SubscriberCard
        subscriber={makeSubscriber({
          status: "fraud_flagged",
          needs_attention: true,
          decline_reason: "Fraud flagged",
        })}
      />
    );
    // Check for "⚠ Fraud flagged" inline warning text
    expect(screen.getByText(/⚠ Fraud flagged/)).toBeInTheDocument();
    // Check for amber border class
    const card = container.firstElementChild;
    expect(card?.className).toContain("border-amber-500");
  });

  it("renders attention styling for needs_attention subscribers", () => {
    const { container } = render(
      <SubscriberCard
        subscriber={makeSubscriber({ needs_attention: true })}
      />
    );
    const card = container.firstElementChild;
    expect(card?.className).toContain("border-amber");
  });
});
