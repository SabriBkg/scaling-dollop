import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useEngineStatus } from "@/hooks/useEngineStatus";

const mockUseAccount = vi.fn();

vi.mock("@/hooks/useAccount", () => ({
  useAccount: () => mockUseAccount(),
}));

describe("useEngineStatus", () => {
  beforeEach(() => {
    mockUseAccount.mockReset();
  });

  it("returns paused when account has no engine_mode", () => {
    mockUseAccount.mockReturnValue({
      data: { engine_mode: null, next_scan_at: null },
    });
    const { result } = renderHook(() => useEngineStatus());
    expect(result.current.mode).toBe("paused");
  });

  it("returns autopilot when engine_active and engine_mode is autopilot", () => {
    mockUseAccount.mockReturnValue({
      data: { engine_active: true, engine_mode: "autopilot", next_scan_at: "2026-04-15T00:00:00Z" },
    });
    const { result } = renderHook(() => useEngineStatus());
    expect(result.current.mode).toBe("autopilot");
    expect(result.current.next_scan_at).toBe("2026-04-15T00:00:00Z");
  });

  it("returns supervised when engine_active and engine_mode is supervised", () => {
    mockUseAccount.mockReturnValue({
      data: { engine_active: true, engine_mode: "supervised", next_scan_at: null },
    });
    const { result } = renderHook(() => useEngineStatus());
    expect(result.current.mode).toBe("supervised");
  });

  it("returns paused when engine_active is false even if engine_mode is set", () => {
    mockUseAccount.mockReturnValue({
      data: { engine_active: false, engine_mode: "autopilot", next_scan_at: null },
    });
    const { result } = renderHook(() => useEngineStatus());
    expect(result.current.mode).toBe("paused");
  });

  it("returns paused when account data is undefined", () => {
    mockUseAccount.mockReturnValue({ data: undefined });
    const { result } = renderHook(() => useEngineStatus());
    expect(result.current.mode).toBe("paused");
    expect(result.current.last_scan_at).toBeNull();
    expect(result.current.next_scan_at).toBeNull();
  });
});
