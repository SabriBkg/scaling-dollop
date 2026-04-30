import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useDpaGate } from "@/hooks/useDpaGate";

const mockUseAccount = vi.fn();

vi.mock("@/hooks/useAccount", () => ({
  useAccount: () => mockUseAccount(),
}));

describe("useDpaGate", () => {
  beforeEach(() => {
    mockUseAccount.mockReset();
  });

  it("treats loading as a neutral state — sendDisabled true, tooltip undefined", () => {
    // While useAccount is loading we must NOT show the AC5 "Sign the DPA"
    // tooltip — already-signed users would see the wrong copy on first paint.
    // We keep sendDisabled true (safer default) but suppress the tooltip.
    mockUseAccount.mockReturnValue({ data: undefined, isLoading: true });
    const { result } = renderHook(() => useDpaGate());
    expect(result.current.dpaAccepted).toBe(false);
    expect(result.current.loading).toBe(true);
    expect(result.current.sendDisabled).toBe(true);
    expect(result.current.tooltip).toBeUndefined();
    expect(result.current.activatePath).toBe("/activate");
  });

  it("enables sends when DPA is accepted (tooltip undefined)", () => {
    mockUseAccount.mockReturnValue({
      data: { dpa_accepted: true, dpa_version: "v1.0-2026-04-29" },
      isLoading: false,
    });
    const { result } = renderHook(() => useDpaGate());
    expect(result.current.dpaAccepted).toBe(true);
    expect(result.current.loading).toBe(false);
    expect(result.current.sendDisabled).toBe(false);
    expect(result.current.tooltip).toBeUndefined();
  });

  it("disables sends with the AC5 tooltip string when DPA is unsigned", () => {
    mockUseAccount.mockReturnValue({
      data: { dpa_accepted: false, dpa_version: null },
      isLoading: false,
    });
    const { result } = renderHook(() => useDpaGate());
    expect(result.current.dpaAccepted).toBe(false);
    expect(result.current.loading).toBe(false);
    expect(result.current.sendDisabled).toBe(true);
    // AC5 contract — must match verbatim.
    expect(result.current.tooltip).toBe("Sign the DPA to enable email sends");
  });
});
