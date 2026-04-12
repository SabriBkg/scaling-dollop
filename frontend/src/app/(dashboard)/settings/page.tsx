"use client";

import { useAccount } from "@/hooks/useAccount";
import { TierBadge } from "@/components/settings/TierBadge";
import { UpgradeCTA } from "@/components/dashboard/UpgradeCTA";

export default function SettingsPage() {
  const { data: account, isLoading } = useAccount();

  return (
    <div>
      <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
        Settings
      </h1>

      <section className="mt-6 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-6">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Subscription
        </h2>

        {isLoading || !account ? (
          <div className="mt-4 h-8 w-48 animate-pulse rounded bg-[var(--surface-sunken)]" />
        ) : (
          <div className="mt-4 space-y-4">
            <div className="flex items-center gap-3">
              <span className="text-sm text-[var(--text-secondary)]">
                Current plan:
              </span>
              <TierBadge account={account} />
            </div>

            {account.is_on_trial && account.trial_days_remaining !== null && (
              <p className="text-sm text-[var(--text-secondary)]">
                Trial ends in {account.trial_days_remaining} days
              </p>
            )}

            {account.tier === "free" && (
              <div className="max-w-xs">
                <UpgradeCTA />
              </div>
            )}

            {account.tier === "mid" && !account.is_on_trial && (
              <p className="text-sm text-[var(--text-secondary)]">
                Manage subscription via Stripe Customer Portal (coming soon)
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
