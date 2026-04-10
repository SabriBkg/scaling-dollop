"use client";

import { useEngineStatus, type EngineStatus } from "@/hooks/useEngineStatus";
import { formatRelativeTime, formatTimeUntil } from "@/lib/formatters";

const DOT_STYLES = {
  autopilot: "bg-[var(--accent-active)] motion-safe:animate-pulse",
  supervised: "bg-[var(--accent-active)] motion-safe:animate-pulse",
  paused: "bg-[var(--accent-neutral)]",
  error: "bg-amber-500",
} as const;

const STATUS_TEXT: Record<EngineStatus["mode"], string> = {
  autopilot: "Autopilot active",
  supervised: "Supervised",
  paused: "Paused",
  error: "Error",
};

export function EngineStatusIndicator() {
  const status = useEngineStatus();

  const dotClass = DOT_STYLES[status.mode];
  const text = STATUS_TEXT[status.mode];

  const subtext =
    status.last_scan_at && status.next_scan_at
      ? `Last scan ${formatRelativeTime(status.last_scan_at)} \u00B7 next in ${formatTimeUntil(status.next_scan_at)}`
      : null;

  const ariaLabel = [
    `Engine status: ${text}`,
    subtext ? `, ${subtext}` : "",
  ].join("");

  return (
    <div
      className="flex items-center gap-2"
      aria-label={ariaLabel}
      role="status"
      aria-live="polite"
    >
      <span className={`inline-block h-2 w-2 rounded-full ${dotClass}`} />
      <div className="hidden md:flex md:flex-col">
        <span className="text-xs font-medium text-[var(--text-primary)]">
          {text}
        </span>
        {subtext && (
          <span className="text-[11px] text-[var(--text-tertiary)]">
            {subtext}
          </span>
        )}
      </div>
    </div>
  );
}
