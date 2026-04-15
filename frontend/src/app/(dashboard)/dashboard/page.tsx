"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useDashboardSummary } from "@/hooks/useDashboardSummary";
import { useSubscribers } from "@/hooks/useSubscribers";
import { StoryArcPanel, StoryArcPanelSkeleton } from "@/components/dashboard/StoryArcPanel";
import { DeclineBreakdown, DeclineBreakdownSkeleton } from "@/components/dashboard/DeclineBreakdown";
import { SubscriberGrid, SubscriberGridSkeleton } from "@/components/dashboard/SubscriberGrid";
import { UpgradeCTA } from "@/components/dashboard/UpgradeCTA";
import { ActivateEngineCTA } from "@/components/dashboard/ActivateEngineCTA";
import { NextScanCountdown } from "@/components/dashboard/NextScanCountdown";

export default function DashboardPage() {
  const { data, isLoading } = useDashboardSummary();
  const { data: subscribers, isLoading: subsLoading } = useSubscribers();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (searchParams.get("upgrade") === "success") {
      queryClient.invalidateQueries({ queryKey: ["account", "me"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      // Clean up the query param
      window.history.replaceState({}, "", "/dashboard");
    }
  }, [searchParams, queryClient]);

  return (
    <div className="flex flex-col gap-6">
      <ActivateEngineCTA />
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
      {subsLoading || !subscribers ? (
        <SubscriberGridSkeleton />
      ) : (
        subscribers.length > 0 && <SubscriberGrid subscribers={subscribers} />
      )}
    </div>
  );
}
