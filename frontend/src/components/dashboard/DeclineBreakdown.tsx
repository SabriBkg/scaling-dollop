"use client";

import type { DeclineBreakdownEntry } from "@/types/dashboard";
import { DeclineCodeExplainer } from "./DeclineCodeExplainer";

interface DeclineBreakdownProps {
  entries: DeclineBreakdownEntry[];
}

export function DeclineBreakdown({ entries }: DeclineBreakdownProps) {
  const sorted = [...entries].sort(
    (a, b) => b.subscriber_count - a.subscriber_count
  );

  return (
    <div className="rounded-xl bg-[var(--bg-surface)] border border-[var(--sn-border)]">
      <div className="px-4 py-3 border-b border-[var(--sn-border)]">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Failure Breakdown
        </h2>
      </div>
      <div className="divide-y divide-[var(--sn-border)]">
        {sorted.map((entry) => (
          <DeclineCodeExplainer key={entry.decline_code} entry={entry} />
        ))}
      </div>
    </div>
  );
}

export function DeclineBreakdownSkeleton() {
  return (
    <div className="rounded-xl bg-[var(--bg-surface)] border border-[var(--sn-border)]">
      <div className="px-4 py-3 border-b border-[var(--sn-border)]">
        <div className="h-4 w-32 rounded bg-[var(--bg-base)] animate-pulse" />
      </div>
      <div className="divide-y divide-[var(--sn-border)]">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="flex items-center justify-between py-3 px-4">
            <div className="flex items-center gap-3">
              <div className="h-2.5 w-2.5 rounded-full bg-[var(--bg-base)] animate-pulse" />
              <div className="h-4 w-28 rounded bg-[var(--bg-base)] animate-pulse" />
            </div>
            <div className="flex items-center gap-6">
              <div className="h-4 w-20 rounded bg-[var(--bg-base)] animate-pulse" />
              <div className="h-4 w-16 rounded bg-[var(--bg-base)] animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
