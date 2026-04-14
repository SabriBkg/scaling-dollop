"use client";

import { useAccount } from "@/hooks/useAccount";

export type EngineStatus = {
  mode: "autopilot" | "supervised" | "paused" | "error";
  last_scan_at: string | null;
  next_scan_at: string | null;
};

export function useEngineStatus(): EngineStatus {
  const { data: account } = useAccount();

  const mode: EngineStatus["mode"] =
    account?.engine_active ? (account.engine_mode ?? "paused") : "paused";

  return {
    mode,
    last_scan_at: null,
    next_scan_at: account?.next_scan_at ?? null,
  };
}
