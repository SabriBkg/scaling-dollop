"use client";

import { useDashboardSummary } from "@/hooks/useDashboardSummary";
import { StoryArcPanel, StoryArcPanelSkeleton } from "@/components/dashboard/StoryArcPanel";
import { DeclineBreakdown, DeclineBreakdownSkeleton } from "@/components/dashboard/DeclineBreakdown";
import { UpgradeCTA } from "@/components/dashboard/UpgradeCTA";

export default function DashboardPage() {
  const { data, isLoading } = useDashboardSummary();

  return (
    <div className="flex flex-col gap-6">
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
