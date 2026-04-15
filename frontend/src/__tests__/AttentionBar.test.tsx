import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AttentionBar } from "@/components/dashboard/AttentionBar";
import type { AttentionItem } from "@/types/dashboard";

const mockItems: AttentionItem[] = [
  {
    type: "fraud_flag",
    subscriber_id: 1,
    subscriber_name: "alice@example.com",
    label: "Fraud flagged: alice@example.com",
  },
  {
    type: "pending_action",
    subscriber_id: 2,
    subscriber_name: "bob@example.com",
    label: "Pending approval: bob@example.com",
  },
];

describe("AttentionBar", () => {
  it("renders when items exist", () => {
    render(<AttentionBar items={mockItems} nextScanAt={null} />);
    expect(
      screen.getByText("2 items need your attention")
    ).toBeInTheDocument();
  });

  it("is hidden when no items", () => {
    const { container } = render(<AttentionBar items={[]} nextScanAt={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders singular text for 1 item", () => {
    render(<AttentionBar items={[mockItems[0]]} nextScanAt={null} />);
    expect(
      screen.getByText("1 item needs your attention")
    ).toBeInTheDocument();
  });

  it("renders action pills for each item", () => {
    render(<AttentionBar items={mockItems} nextScanAt={null} />);
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("bob@example.com")).toBeInTheDocument();
  });

  it("has correct accessibility attributes", () => {
    render(<AttentionBar items={mockItems} nextScanAt={null} />);
    const bar = screen.getByRole("alert");
    expect(bar).toBeInTheDocument();
    expect(bar).toHaveAttribute("aria-live", "polite");
  });

  it("shows countdown when nextScanAt is provided", () => {
    const future = new Date(Date.now() + 30 * 60_000).toISOString();
    render(<AttentionBar items={mockItems} nextScanAt={future} />);
    expect(
      screen.getByText(/Review before next engine cycle/)
    ).toBeInTheDocument();
  });
});
