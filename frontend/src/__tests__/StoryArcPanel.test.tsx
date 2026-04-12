import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StoryArcPanel, StoryArcPanelSkeleton } from "@/components/dashboard/StoryArcPanel";
import type { DashboardSummary } from "@/types/dashboard";

// Mock useAccount (used by UpgradeCTA, which may be in tree)
vi.mock("@/hooks/useAccount", () => ({
  useAccount: () => ({ data: null, isLoading: false }),
}));

const mockData: DashboardSummary = {
  total_failures: 42,
  total_subscribers: 18,
  estimated_recoverable_cents: 64000,
  recovered_this_month_cents: 12000,
  recovered_count: 5,
  recovery_rate: 27.8,
  net_benefit_cents: 12000,
  decline_breakdown: [],
};

describe("StoryArcPanel", () => {
  it("renders 3 columns with role=region", () => {
    render(<StoryArcPanel data={mockData} />);
    const regions = screen.getAllByRole("region");
    expect(regions).toHaveLength(3);
  });

  it("renders column aria-labels", () => {
    render(<StoryArcPanel data={mockData} />);
    expect(screen.getByLabelText("Failures detected")).toBeInTheDocument();
    expect(screen.getByLabelText("Recovery in progress")).toBeInTheDocument();
    expect(screen.getByLabelText("Revenue recovered")).toBeInTheDocument();
  });

  it("renders correct data in Column 1 (Detected)", () => {
    render(<StoryArcPanel data={mockData} />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("18 subscribers")).toBeInTheDocument();
  });

  it("renders estimated recoverable in Column 2", () => {
    render(<StoryArcPanel data={mockData} />);
    expect(screen.getByText("$640.00")).toBeInTheDocument();
    expect(screen.getByText("27.8% recovery rate")).toBeInTheDocument();
  });

  it("renders recovered amount in Column 3", () => {
    render(<StoryArcPanel data={mockData} />);
    expect(screen.getByText("$120.00")).toBeInTheDocument();
  });

  it("has aria-labels with currency context on KPI numbers", () => {
    render(<StoryArcPanel data={mockData} />);
    expect(
      screen.getByLabelText("$640.00 estimated recoverable revenue")
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("$120.00 recovered this month")
    ).toBeInTheDocument();
  });

  it("renders step badges", () => {
    render(<StoryArcPanel data={mockData} />);
    expect(screen.getByText("Detected")).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument();
    expect(screen.getByText("Recovered")).toBeInTheDocument();
  });
});

describe("StoryArcPanelSkeleton", () => {
  it("renders 3 skeleton columns", () => {
    const { container } = render(<StoryArcPanelSkeleton />);
    const pulseElements = container.querySelectorAll(".animate-pulse");
    expect(pulseElements.length).toBeGreaterThanOrEqual(6);
  });
});
