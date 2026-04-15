"use client";

import { useDashboardSummary } from "@/hooks/useDashboardSummary";
import { useEngineStatus } from "@/hooks/useEngineStatus";
import { AttentionBar } from "@/components/dashboard/AttentionBar";

export function DashboardAttentionBar() {
  const { data } = useDashboardSummary();
  const { next_scan_at } = useEngineStatus();

  if (!data || data.attention_items.length === 0) return null;

  return (
    <AttentionBar items={data.attention_items} nextScanAt={next_scan_at} />
  );
}
