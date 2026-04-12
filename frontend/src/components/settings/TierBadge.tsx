"use client";

import type { Account } from "@/types";

interface TierBadgeProps {
  account: Account;
}

export function TierBadge({ account }: TierBadgeProps) {
  const { tier, is_on_trial, trial_days_remaining } = account;

  let label: string;
  let colorVar: string;

  switch (tier) {
    case "free":
      label = "Free";
      colorVar = "var(--text-secondary)";
      break;
    case "mid":
      if (is_on_trial && trial_days_remaining !== null) {
        label = `Mid — Trial (${trial_days_remaining}d left)`;
      } else {
        label = "Mid";
      }
      colorVar = "var(--accent-active)";
      break;
    case "pro":
      label = "Pro";
      colorVar = "var(--accent-recovery)";
      break;
    default:
      label = tier;
      colorVar = "var(--text-secondary)";
  }

  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: `color-mix(in srgb, ${colorVar} 15%, transparent)`,
        color: colorVar,
      }}
    >
      {label}
    </span>
  );
}
