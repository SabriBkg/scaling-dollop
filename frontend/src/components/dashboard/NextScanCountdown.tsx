"use client";

import { useAccount } from "@/hooks/useAccount";

export function NextScanCountdown() {
  const { data: account } = useAccount();

  if (!account || account.tier !== "free" || !account.next_scan_at) {
    return null;
  }

  const nextScan = new Date(account.next_scan_at);
  const now = new Date();
  const diffMs = nextScan.getTime() - now.getTime();
  const diffDays = Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-4">
      <p className="text-sm font-medium text-[var(--text-secondary)]">
        Your next scan is in{" "}
        <span className="text-lg font-semibold text-[var(--text-primary)]">
          {diffDays} {diffDays === 1 ? "day" : "days"}
        </span>
      </p>
    </div>
  );
}
