"use client";

import { cn } from "@/lib/utils";
import type { SubscriberCard } from "@/types/subscriber";

const badgeConfig = {
  recovered: {
    label: "Recovered",
    className: "bg-[var(--accent-recovery)]/15 text-[var(--accent-recovery)]",
  },
  active: {
    label: "Active",
    className: "bg-[var(--accent-active)]/15 text-[var(--accent-active)]",
  },
  fraud_flagged: {
    label: "Fraud Flagged",
    className: "bg-[var(--accent-fraud)]/15 text-[var(--accent-fraud)]",
  },
  passive_churn: {
    label: "Passive Churn",
    className: "bg-[var(--accent-neutral)]/15 text-[var(--accent-neutral)]",
  },
} as const;

interface StatusBadgeProps {
  status: SubscriberCard["status"];
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = badgeConfig[status];

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5",
        "text-[11px] font-medium leading-tight",
        config.className
      )}
      aria-label={`Status: ${config.label}`}
    >
      {config.label}
    </span>
  );
}
