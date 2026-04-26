import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn(), back: vi.fn(), forward: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
}));

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
    render(<AttentionBar items={[]} nextScanAt={null} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
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

  it("returns empty countdown for invalid nextScanAt", () => {
    render(<AttentionBar items={mockItems} nextScanAt="not-a-date" />);
    expect(
      screen.queryByText(/Review before next engine cycle/)
    ).not.toBeInTheDocument();
  });

  it("navigates to review queue when a pending_action pill is clicked", () => {
    mockPush.mockClear();
    render(<AttentionBar items={mockItems} nextScanAt={null} />);
    fireEvent.click(screen.getByText("bob@example.com"));
    expect(mockPush).toHaveBeenCalledWith("/review-queue");
  });

  it("does not navigate when a fraud_flag pill is clicked", () => {
    mockPush.mockClear();
    render(<AttentionBar items={mockItems} nextScanAt={null} />);
    fireEvent.click(screen.getByText("alice@example.com"));
    expect(mockPush).not.toHaveBeenCalled();
  });
});
