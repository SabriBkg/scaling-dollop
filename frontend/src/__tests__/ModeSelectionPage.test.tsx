// v1: mode selection is removed. The page is now a redirect-only stub
// that sends any stale browser tab back to /dashboard.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import ModeSelectionPage from "@/app/(dashboard)/activate/mode/page";

const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
}));

describe("ModeSelectionPage (v1 redirect stub)", () => {
  beforeEach(() => {
    mockReplace.mockReset();
  });

  it("redirects to /dashboard on mount", async () => {
    render(<ModeSelectionPage />);
    // useEffect runs post-commit; waitFor guards against future async guards
    // that would defer the redirect (the test would otherwise pass by checking
    // before the effect runs).
    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith("/dashboard"),
    );
  });

  it("renders a loading spinner so a stale tab does not flash empty", () => {
    const { container } = render(<ModeSelectionPage />);
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });
});
