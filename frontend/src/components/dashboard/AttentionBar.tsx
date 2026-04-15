"use client";

import { cn } from "@/lib/utils";
import type { AttentionItem } from "@/types/dashboard";

interface AttentionBarProps {
  items: AttentionItem[];
  nextScanAt: string | null;
}

function formatCountdown(nextScanAt: string | null): string {
  if (!nextScanAt) return "";
  const diff = new Date(nextScanAt).getTime() - Date.now();
  if (diff <= 0) return "imminently";
  const minutes = Math.ceil(diff / 60_000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

export function AttentionBar({ items, nextScanAt }: AttentionBarProps) {
  if (items.length === 0) return null;

  const hasFraud = items.some((i) => i.type === "fraud_flag");
  const countdown = formatCountdown(nextScanAt);

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-6 py-2.5 text-sm",
        hasFraud
          ? "bg-amber-100 dark:bg-amber-950"
          : "bg-amber-50 dark:bg-amber-950/60"
      )}
      role="alert"
      aria-live="polite"
    >
      <span className="text-amber-600 dark:text-amber-400 text-base flex-shrink-0">
        ⚠
      </span>

      <span className="font-semibold text-amber-900 dark:text-amber-200">
        {items.length} {items.length === 1 ? "item needs" : "items need"} your
        attention
      </span>

      {countdown && (
        <span className="text-amber-700/80 dark:text-amber-300/70 hidden sm:inline">
          · Review before next engine cycle in {countdown}
        </span>
      )}

      <div className="ml-auto flex items-center gap-2 flex-shrink-0 overflow-x-auto">
        {items.map((item) => (
          <button
            key={`${item.type}-${item.subscriber_id}`}
            className={cn(
              "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium",
              "bg-amber-200/60 dark:bg-amber-800/60",
              "text-amber-900 dark:text-amber-100",
              "hover:bg-amber-300/80 dark:hover:bg-amber-700/80",
              "transition-colors whitespace-nowrap"
            )}
            onClick={() => {
              // Navigate to subscriber detail or review queue — Story 5.1
            }}
          >
            {item.subscriber_name}
          </button>
        ))}
      </div>
    </div>
  );
}
