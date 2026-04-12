"use client";

import type { DeclineBreakdownEntry } from "@/types/dashboard";
import { formatCurrency } from "@/lib/formatters";

const actionColorMap: Record<string, string> = {
  retry_notify: "bg-[var(--accent-recovery)]",
  notify_only: "bg-amber-400",
  fraud_flag: "bg-[var(--accent-fraud)]",
  no_action: "bg-[var(--accent-neutral)]",
};

interface DeclineCodeExplainerProps {
  entry: DeclineBreakdownEntry;
}

export function DeclineCodeExplainer({ entry }: DeclineCodeExplainerProps) {
  const dotColor = actionColorMap[entry.recovery_action] || actionColorMap.no_action;

  return (
    <div className="flex items-center justify-between py-3 px-4">
      <div className="flex items-center gap-3">
        <span className={`h-2.5 w-2.5 rounded-full flex-shrink-0 ${dotColor}`} />
        <span className="text-sm font-medium text-[var(--text-primary)]">
          {entry.human_label}
        </span>
      </div>
      <div className="flex items-center gap-6 text-sm text-[var(--text-secondary)]">
        <span style={{ fontVariantNumeric: "tabular-nums" }}>
          {entry.subscriber_count} {entry.subscriber_count === 1 ? "subscriber" : "subscribers"}
        </span>
        <span
          className="font-medium text-[var(--text-primary)]"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {formatCurrency(entry.total_amount_cents)}
        </span>
      </div>
    </div>
  );
}
