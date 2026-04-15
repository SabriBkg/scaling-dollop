"use client";

import { useMemo } from "react";
import { SubscriberCard } from "@/components/dashboard/SubscriberCard";
import type { SubscriberCard as SubscriberCardType } from "@/types/subscriber";

interface SubscriberGridProps {
  subscribers: SubscriberCardType[];
}

function SubscriberGridSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="rounded-lg border border-[var(--sn-border)] bg-[var(--bg-surface)] p-4 animate-pulse"
        >
          <div className="h-4 bg-[var(--sn-border)] rounded w-3/4 mb-2" />
          <div className="h-3 bg-[var(--sn-border)] rounded w-1/2 mb-3" />
          <div className="flex justify-between">
            <div className="h-3 bg-[var(--sn-border)] rounded w-2/5" />
            <div className="h-5 bg-[var(--sn-border)] rounded-full w-16" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function SubscriberGrid({ subscribers }: SubscriberGridProps) {
  // Client-side sorting guarantee: attention-state first, then by status
  const sorted = useMemo(() => {
    return [...subscribers].sort((a, b) => {
      const aAttention = a.needs_attention ? 0 : 1;
      const bAttention = b.needs_attention ? 0 : 1;
      if (aAttention !== bAttention) return aAttention - bAttention;
      return 0; // Preserve server ordering otherwise
    });
  }, [subscribers]);

  return (
    <section>
      <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-3">
        Subscribers
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {sorted.map((sub) => (
          <SubscriberCard key={sub.id} subscriber={sub} />
        ))}
      </div>
    </section>
  );
}

export { SubscriberGridSkeleton };
