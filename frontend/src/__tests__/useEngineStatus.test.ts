import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useEngineStatus } from "@/hooks/useEngineStatus";

describe("useEngineStatus", () => {
  it("returns paused stub by default", () => {
    const { result } = renderHook(() => useEngineStatus());
    expect(result.current.mode).toBe("paused");
    expect(result.current.last_scan_at).toBeNull();
    expect(result.current.next_scan_at).toBeNull();
  });
});
