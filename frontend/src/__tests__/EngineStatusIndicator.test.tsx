import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { EngineStatusIndicator } from "@/components/common/EngineStatusIndicator";

vi.mock("@/hooks/useEngineStatus", () => ({
  useEngineStatus: vi.fn(),
}));

import { useEngineStatus } from "@/hooks/useEngineStatus";
const mockUseEngineStatus = vi.mocked(useEngineStatus);

describe("EngineStatusIndicator", () => {
  it("renders paused state with grey dot", () => {
    mockUseEngineStatus.mockReturnValue({
      mode: "paused",
      last_scan_at: null,
      next_scan_at: null,
    });

    const { container } = render(<EngineStatusIndicator />);
    const dot = container.querySelector("span.rounded-full");
    expect(dot?.className).toContain("accent-neutral");
    expect(screen.getByText("Paused")).toBeInTheDocument();
  });

  it("renders autopilot state with animated blue dot", () => {
    mockUseEngineStatus.mockReturnValue({
      mode: "autopilot",
      last_scan_at: new Date(Date.now() - 18 * 60 * 1000).toISOString(),
      next_scan_at: new Date(Date.now() + 42 * 60 * 1000).toISOString(),
    });

    const { container } = render(<EngineStatusIndicator />);
    const dot = container.querySelector("span.rounded-full");
    expect(dot?.className).toContain("accent-active");
    expect(dot?.className).toContain("animate-pulse");
    expect(screen.getByText("Autopilot active")).toBeInTheDocument();
  });

  it("renders error state with amber dot", () => {
    mockUseEngineStatus.mockReturnValue({
      mode: "error",
      last_scan_at: null,
      next_scan_at: null,
    });

    const { container } = render(<EngineStatusIndicator />);
    const dot = container.querySelector("span.rounded-full");
    expect(dot?.className).toContain("amber");
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("has aria-live polite for accessibility", () => {
    mockUseEngineStatus.mockReturnValue({
      mode: "paused",
      last_scan_at: null,
      next_scan_at: null,
    });

    render(<EngineStatusIndicator />);
    const statusEl = screen.getByRole("status");
    expect(statusEl).toHaveAttribute("aria-live", "polite");
  });
});
