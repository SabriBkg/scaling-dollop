"use client";

import { useDashboardSummary } from "@/hooks/useDashboardSummary";
import { StoryArcPanel, StoryArcPanelSkeleton } from "@/components/dashboard/StoryArcPanel";
import { DeclineBreakdown, DeclineBreakdownSkeleton } from "@/components/dashboard/DeclineBreakdown";
import { UpgradeCTA } from "@/components/dashboard/UpgradeCTA";
import { NextScanCountdown } from "@/components/dashboard/NextScanCountdown";

export default function DashboardPage() {
  const { data, isLoading } = useDashboardSummary();

  return (
    <div className="flex flex-col gap-6">
      <NextScanCountdown />
      {isLoading || !data ? (
        <>
          <StoryArcPanelSkeleton />
          <DeclineBreakdownSkeleton />
        </>
      ) : (
        <>
          <StoryArcPanel data={data} column2Footer={<UpgradeCTA />} />
          {data.decline_breakdown.length > 0 && (
            <DeclineBreakdown entries={data.decline_breakdown} />
          )}
        </>
      )}
    </div>
  );
}
