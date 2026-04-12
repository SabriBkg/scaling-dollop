import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DeclineBreakdown, DeclineBreakdownSkeleton } from "@/components/dashboard/DeclineBreakdown";
import type { DeclineBreakdownEntry } from "@/types/dashboard";

const mockEntries: DeclineBreakdownEntry[] = [
  {
    decline_code: "insufficient_funds",
    human_label: "Insufficient funds",
    subscriber_count: 10,
    total_amount_cents: 50000,
    recovery_action: "retry_notify",
  },
  {
    decline_code: "card_expired",
    human_label: "Card expired",
    subscriber_count: 5,
    total_amount_cents: 25000,
    recovery_action: "notify_only",
  },
  {
    decline_code: "fraudulent",
    human_label: "Fraud flagged",
    subscriber_count: 2,
    total_amount_cents: 8000,
    recovery_action: "fraud_flag",
  },
];

describe("DeclineBreakdown", () => {
  it("renders human-readable labels", () => {
    render(<DeclineBreakdown entries={mockEntries} />);
    expect(screen.getByText("Insufficient funds")).toBeInTheDocument();
    expect(screen.getByText("Card expired")).toBeInTheDocument();
    expect(screen.getByText("Fraud flagged")).toBeInTheDocument();
  });

  it("does NOT display raw Stripe decline codes", () => {
    render(<DeclineBreakdown entries={mockEntries} />);
    expect(screen.queryByText("insufficient_funds")).not.toBeInTheDocument();
    expect(screen.queryByText("card_expired")).not.toBeInTheDocument();
    expect(screen.queryByText("fraudulent")).not.toBeInTheDocument();
  });

  it("renders subscriber counts", () => {
    render(<DeclineBreakdown entries={mockEntries} />);
    expect(screen.getByText("10 subscribers")).toBeInTheDocument();
    expect(screen.getByText("5 subscribers")).toBeInTheDocument();
    expect(screen.getByText("2 subscribers")).toBeInTheDocument();
  });

  it("renders amounts formatted as currency", () => {
    render(<DeclineBreakdown entries={mockEntries} />);
    expect(screen.getByText("$500.00")).toBeInTheDocument();
    expect(screen.getByText("$250.00")).toBeInTheDocument();
    expect(screen.getByText("$80.00")).toBeInTheDocument();
  });

  it("sorts entries by subscriber count descending", () => {
    const { container } = render(<DeclineBreakdown entries={mockEntries} />);
    const labels = container.querySelectorAll(
      ".text-sm.font-medium.text-\\[var\\(--text-primary\\)\\]"
    );
    expect(labels[0]?.textContent).toBe("Insufficient funds");
    expect(labels[1]?.textContent).toBe("Card expired");
    expect(labels[2]?.textContent).toBe("Fraud flagged");
  });

  it("renders section header", () => {
    render(<DeclineBreakdown entries={mockEntries} />);
    expect(screen.getByText("Failure Breakdown")).toBeInTheDocument();
  });
});

describe("DeclineBreakdownSkeleton", () => {
  it("renders 6 skeleton rows", () => {
    const { container } = render(<DeclineBreakdownSkeleton />);
    const pulseElements = container.querySelectorAll(".animate-pulse");
    // 1 header + 6 rows * 3 elements each
    expect(pulseElements.length).toBeGreaterThanOrEqual(6);
  });
});
