"use client";

export type EngineStatus = {
  mode: "autopilot" | "supervised" | "paused" | "error";
  last_scan_at: string | null;
  next_scan_at: string | null;
};

// Stub until engine status API exists (Story 3.1+)
export function useEngineStatus(): EngineStatus {
  return {
    mode: "paused",
    last_scan_at: null,
    next_scan_at: null,
  };
}
