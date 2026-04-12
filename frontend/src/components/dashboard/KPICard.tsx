"use client";

import { cn } from "@/lib/utils";

const colorMap = {
  neutral: "text-[var(--text-primary)]",
  blue: "text-[var(--accent-active)]",
  green: "text-[var(--accent-recovery)]",
} as const;

interface KPICardProps {
  label: string;
  value: number;
  formattedValue: string;
  supportingText?: string;
  color?: keyof typeof colorMap;
  ariaLabel: string;
  heroSize?: string;
}

export function KPICard({
  label,
  formattedValue,
  supportingText,
  color = "neutral",
  ariaLabel,
  heroSize = "text-4xl",
}: KPICardProps) {
  return (
    <div className="flex flex-col gap-1 focus-within:outline-2 focus-within:outline-[var(--accent-active)] rounded-md">
      <span className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
        {label}
      </span>
      <span
        className={cn(
          heroSize,
          "font-bold leading-tight",
          "focus:outline-2 focus:outline-[var(--accent-active)] rounded",
          colorMap[color]
        )}
        style={{ fontVariantNumeric: "tabular-nums" }}
        aria-label={ariaLabel}
        tabIndex={0}
        role="text"
      >
        {formattedValue}
      </span>
      {supportingText && (
        <span className="text-sm text-[var(--text-secondary)]">
          {supportingText}
        </span>
      )}
    </div>
  );
}
