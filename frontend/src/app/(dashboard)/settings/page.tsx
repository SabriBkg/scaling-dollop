"use client";

import Link from "next/link";
import { Shield } from "lucide-react";
import { useAccount } from "@/hooks/useAccount";
import { TierBadge } from "@/components/settings/TierBadge";
import { ToneSelector } from "@/components/settings/ToneSelector";
import { NotificationPreview } from "@/components/settings/NotificationPreview";
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

      {account && account.tier !== "free" && (
        <section className="mt-6 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-6">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-[var(--accent-active)]" />
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">
              Data Processing Agreement
            </h2>
          </div>

          {account.dpa_accepted_at ? (
            <div className="mt-4 space-y-1 text-sm">
              <p className="text-[var(--text-primary)]">
                Signed on{" "}
                {new Date(account.dpa_accepted_at).toLocaleDateString()}
              </p>
              <p className="text-[var(--text-secondary)]">
                Version {account.dpa_version ?? "v0-legacy"}
              </p>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              <p className="text-sm text-[var(--text-secondary)]">
                You must sign the Data Processing Agreement before SafeNet can
                send dunning emails to your subscribers.
              </p>
              <Link
                href="/activate"
                className="inline-block rounded-lg bg-[var(--cta)] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[var(--cta-hover)] focus:outline-2 focus:outline-offset-2 focus:outline-[var(--accent-active)]"
              >
                Sign the Data Processing Agreement
              </Link>
            </div>
          )}
        </section>
      )}

      {account && (
        <section className="mt-6 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-6">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Notifications
          </h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Choose the voice your subscribers see in payment failure emails.
          </p>
          <div className="mt-4 grid gap-6 md:grid-cols-2">
            <ToneSelector
              account={account}
              value={account.notification_tone}
              onChange={() => {}}
              disabled={
                account.tier === "free" ||
                !account.dpa_accepted
              }
              disabledHint={
                account.tier === "free"
                  ? "Upgrade to Mid or Pro to customize your subscriber notifications."
                  : !account.dpa_accepted
                    ? "Accept the Data Processing Agreement to enable tone selection."
                    : undefined
              }
            />
            <NotificationPreview tone={account.notification_tone} />
          </div>
        </section>
      )}
    </div>
  );
}
