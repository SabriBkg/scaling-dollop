import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "@/components/subscriber/StatusBadge";

describe("StatusBadge", () => {
  it("renders Recovered variant with correct label", () => {
    render(<StatusBadge status="recovered" />);
    expect(screen.getByText("Recovered")).toBeInTheDocument();
    expect(screen.getByText("Recovered")).toHaveAttribute(
      "aria-label",
      "Status: Recovered"
    );
  });

  it("renders Active variant with correct label", () => {
    render(<StatusBadge status="active" />);
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Active")).toHaveAttribute(
      "aria-label",
      "Status: Active"
    );
  });

  it("renders Fraud Flagged variant with correct label", () => {
    render(<StatusBadge status="fraud_flagged" />);
    expect(screen.getByText("Fraud Flagged")).toBeInTheDocument();
    expect(screen.getByText("Fraud Flagged")).toHaveAttribute(
      "aria-label",
      "Status: Fraud Flagged"
    );
  });

  it("renders Passive Churn variant with correct label", () => {
    render(<StatusBadge status="passive_churn" />);
    expect(screen.getByText("Passive Churn")).toBeInTheDocument();
    expect(screen.getByText("Passive Churn")).toHaveAttribute(
      "aria-label",
      "Status: Passive Churn"
    );
  });

  it("always renders text label alongside color", () => {
    const statusLabels = [
      ["recovered", "Recovered"],
      ["active", "Active"],
      ["fraud_flagged", "Fraud Flagged"],
      ["passive_churn", "Passive Churn"],
    ] as const;
    for (const [status, label] of statusLabels) {
      const { unmount } = render(<StatusBadge status={status} />);
      // Verify the badge has visible text content (never color-only)
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });
});
