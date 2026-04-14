"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEngineStatus } from "@/hooks/useEngineStatus";
import { useDashboardSummary } from "@/hooks/useDashboardSummary";
import { ROUTES } from "@/lib/constants";
import { WorkspaceIdentity } from "./WorkspaceIdentity";
import { EngineStatusIndicator } from "./EngineStatusIndicator";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";

interface NavTab {
  label: string;
  href: string;
  show?: boolean;
}

export function NavBar() {
  const pathname = usePathname();
  const engineStatus = useEngineStatus();
  const { data: dashboardData } = useDashboardSummary();
  const pendingCount =
    engineStatus.mode === "supervised"
      ? dashboardData?.pending_action_count ?? 0
      : 0;

  const tabs: NavTab[] = [
    { label: "Dashboard", href: ROUTES.DASHBOARD },
    { label: "Settings", href: ROUTES.SETTINGS },
    {
      label: "Review Queue",
      href: ROUTES.REVIEW_QUEUE,
      show: engineStatus.mode === "supervised",
    },
  ];

  const visibleTabs = tabs.filter((tab) => tab.show !== false);

  return (
    <header className="h-12 border-b border-[var(--sn-border)] bg-[var(--bg-surface)]">
      <div className="mx-auto flex h-full max-w-[1280px] items-center justify-between px-4">
        {/* Left: Workspace Identity */}
        <WorkspaceIdentity />

        {/* Center: Navigation Tabs */}
        <nav className="hidden md:flex md:items-center md:gap-1">
          {visibleTabs.map((tab) => {
            const isActive = pathname.startsWith(tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`relative px-3 py-3.5 text-sm transition-colors ${
                  isActive
                    ? "font-semibold text-[var(--text-primary)]"
                    : "font-normal text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                {tab.label}
                {tab.href === ROUTES.REVIEW_QUEUE && pendingCount > 0 && (
                  <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--accent-active)] px-1.5 text-xs font-medium text-white">
                    {pendingCount}
                  </span>
                )}
                {isActive && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--accent-active)]" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right: Engine Status + Theme Toggle + User Menu */}
        <div className="flex items-center gap-2">
          <EngineStatusIndicator />
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
