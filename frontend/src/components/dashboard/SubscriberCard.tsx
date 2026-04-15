"use client";

import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/subscriber/StatusBadge";
import type { SubscriberCard as SubscriberCardType } from "@/types/subscriber";

interface SubscriberCardProps {
  subscriber: SubscriberCardType;
}

export function SubscriberCard({ subscriber }: SubscriberCardProps) {
  const isFraud = subscriber.status === "fraud_flagged";
  const isRecovered = subscriber.status === "recovered";
  const isAttention = subscriber.needs_attention;

  const formattedAmount = subscriber.amount_cents != null
    ? `$${(subscriber.amount_cents / 100).toFixed(2)}`
    : null;

  return (
    <div
      className={cn(
        "rounded-lg border p-4 transition-colors cursor-pointer",
        "bg-[var(--bg-surface)] border-[var(--sn-border)]",
        "hover:border-[var(--text-secondary)]",
        isFraud && "border-amber-500 border-2",
        isAttention && !isFraud && "border-amber-400"
      )}
      onClick={() => {
        // Subscriber detail navigation — Story 5.1
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-bold text-sm text-[var(--text-primary)] truncate">
          {subscriber.email || subscriber.stripe_customer_id}
        </span>
        {formattedAmount && (
          <span
            className={cn(
              "text-sm font-semibold tabular-nums whitespace-nowrap",
              isRecovered
                ? "text-[var(--accent-recovery)]"
                : "text-[var(--text-primary)]"
            )}
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {formattedAmount}
          </span>
        )}
      </div>

      <span className="text-xs text-[var(--text-secondary)] truncate block mt-0.5">
        {subscriber.email && subscriber.stripe_customer_id}
      </span>

      <div className="flex items-center justify-between gap-2 mt-2">
        <span className="text-xs text-[var(--text-secondary)] truncate">
          {isFraud && (
            <span className="text-amber-600 font-medium">
              {"⚠ Fraud flagged · "}
            </span>
          )}
          {subscriber.decline_reason || "—"}
        </span>
        <StatusBadge status={subscriber.status} />
      </div>
    </div>
  );
}
