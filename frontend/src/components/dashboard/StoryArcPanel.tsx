"use client";

import type { DashboardSummary } from "@/types/dashboard";
import { formatCurrency } from "@/lib/formatters";
import { KPICard } from "./KPICard";

interface StoryArcPanelProps {
  data: DashboardSummary;
  column2Footer?: React.ReactNode;
}

function StepBadge({ step, label }: { step: number; label: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--bg-base)] text-xs font-semibold text-[var(--text-secondary)]">
        {step}
      </span>
      <span className="text-sm font-medium text-[var(--text-secondary)]">
        {label}
      </span>
    </div>
  );
}

export function StoryArcPanel({ data, column2Footer }: StoryArcPanelProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--sn-border)]">
      {/* Column 1: Detected */}
      <div
        role="region"
        aria-label="Failures detected"
        className="p-6 border-b lg:border-b-0 lg:border-r border-[var(--sn-border)]"
      >
        <StepBadge step={1} label="Detected" />
        <KPICard
          label="Total failures"
          value={data.total_failures}
          formattedValue={data.total_failures.toLocaleString()}
          supportingText={`${data.total_subscribers.toLocaleString()} subscribers`}
          color="neutral"
          ariaLabel={`${data.total_failures} total failures detected`}
          heroSize="text-4xl"
        />
      </div>

      {/* Column 2: In Progress */}
      <div
        role="region"
        aria-label="Recovery in progress"
        className="p-6 border-b lg:border-b-0 lg:border-r border-[var(--sn-border)]"
      >
        <StepBadge step={2} label="In Progress" />
        <KPICard
          label="Estimated recoverable"
          value={data.estimated_recoverable_cents}
          formattedValue={formatCurrency(data.estimated_recoverable_cents)}
          supportingText={`${data.recovery_rate}% recovery rate`}
          color="blue"
          ariaLabel={`${formatCurrency(data.estimated_recoverable_cents)} estimated recoverable revenue`}
          heroSize="text-[52px]"
        />
        {column2Footer}
      </div>

      {/* Column 3: Recovered */}
      <div
        role="region"
        aria-label="Revenue recovered"
        className="p-6"
      >
        <StepBadge step={3} label="Recovered" />
        <KPICard
          label="Recovered this month"
          value={data.recovered_this_month_cents}
          formattedValue={formatCurrency(data.recovered_this_month_cents)}
          supportingText={`${data.recovered_count} recovered \u00B7 ${formatCurrency(data.net_benefit_cents)} net benefit`}
          color="green"
          ariaLabel={`${formatCurrency(data.recovered_this_month_cents)} recovered this month`}
          heroSize="text-[56px]"
        />
      </div>
    </div>
  );
}

const skeletonHeroHeights = ["h-9", "h-[52px]", "h-[56px]"] as const;

export function StoryArcPanelSkeleton() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--sn-border)]">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className={`p-6 ${i < 3 ? "border-b lg:border-b-0 lg:border-r border-[var(--sn-border)]" : ""}`}
        >
          <div className="flex items-center gap-2 mb-3">
            <div className="h-6 w-6 rounded-full bg-[var(--bg-base)] animate-pulse" />
            <div className="h-4 w-20 rounded bg-[var(--bg-base)] animate-pulse" />
          </div>
          <div className="flex flex-col gap-2">
            <div className="h-3 w-24 rounded bg-[var(--bg-base)] animate-pulse" />
            <div className={`${skeletonHeroHeights[i - 1]} w-40 rounded bg-[var(--bg-base)] animate-pulse`} />
            <div className="h-4 w-32 rounded bg-[var(--bg-base)] animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  );
}
