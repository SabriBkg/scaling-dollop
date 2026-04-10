import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeToggle } from "@/components/common/ThemeToggle";

const mockSetTheme = vi.fn();
vi.mock("next-themes", () => ({
  useTheme: () => ({
    resolvedTheme: "light",
    setTheme: mockSetTheme,
  }),
}));

vi.mock("@/stores/uiStore", () => ({
  useUIStore: (selector: (s: { setThemePreference: typeof vi.fn }) => unknown) =>
    selector({ setThemePreference: vi.fn() }),
}));

describe("ThemeToggle", () => {
  it("renders toggle button with aria-label", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: "Toggle theme" });
    expect(button).toBeInTheDocument();
  });

  it("toggles theme on click", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: "Toggle theme" });
    fireEvent.click(button);
    expect(mockSetTheme).toHaveBeenCalledWith("dark");
  });
});
