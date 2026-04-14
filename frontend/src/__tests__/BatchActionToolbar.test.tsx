import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BatchActionToolbar } from "@/components/review/BatchActionToolbar";

describe("BatchActionToolbar", () => {
  const defaultProps = {
    selectedCount: 3,
    onApprove: vi.fn(),
    onExclude: vi.fn(),
    onDeselectAll: vi.fn(),
    isApproving: false,
  };

  it("renders with selection count", () => {
    render(<BatchActionToolbar {...defaultProps} />);
    expect(screen.getByText("3 subscribers selected")).toBeInTheDocument();
    expect(screen.getByText("Apply recommended actions")).toBeInTheDocument();
  });

  it("hides when no rows selected", () => {
    const { container } = render(
      <BatchActionToolbar {...defaultProps} selectedCount={0} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("shows singular for single selection", () => {
    render(<BatchActionToolbar {...defaultProps} selectedCount={1} />);
    expect(screen.getByText("1 subscriber selected")).toBeInTheDocument();
  });

  it("calls onApprove when approve clicked", () => {
    render(<BatchActionToolbar {...defaultProps} />);
    fireEvent.click(screen.getByText("Apply recommended actions"));
    expect(defaultProps.onApprove).toHaveBeenCalled();
  });

  it("calls onDeselectAll when deselect clicked", () => {
    render(<BatchActionToolbar {...defaultProps} />);
    fireEvent.click(screen.getByText("Deselect all"));
    expect(defaultProps.onDeselectAll).toHaveBeenCalled();
  });

  it("has toolbar role", () => {
    render(<BatchActionToolbar {...defaultProps} />);
    expect(screen.getByRole("toolbar")).toBeInTheDocument();
  });

  it("shows loading state when approving", () => {
    render(<BatchActionToolbar {...defaultProps} isApproving={true} />);
    expect(screen.getByText("Applying…")).toBeInTheDocument();
  });
});
