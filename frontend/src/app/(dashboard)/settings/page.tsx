"use client";

import { useState } from "react";
import { useAccount } from "@/hooks/useAccount";
import { useQueryClient } from "@tanstack/react-query";
import { TierBadge } from "@/components/settings/TierBadge";
import { UpgradeCTA } from "@/components/dashboard/UpgradeCTA";
import { toast } from "sonner";
import api from "@/lib/api";
import type { Account, ApiResponse } from "@/types";

export default function SettingsPage() {
  const { data: account, isLoading } = useAccount();
  const queryClient = useQueryClient();
  const [isSwitching, setIsSwitching] = useState(false);

  const handleModeChange = async (mode: "autopilot" | "supervised") => {
    if (!account || account.engine_mode === mode) return;
    setIsSwitching(true);
    try {
      const { data } = await api.post<ApiResponse<Account>>("/account/engine/mode/", { mode });
      queryClient.setQueryData(["account", "me"], data.data);
      queryClient.invalidateQueries({ queryKey: ["account", "me"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      queryClient.invalidateQueries({ queryKey: ["actions", "pending"] });
      queryClient.invalidateQueries({ queryKey: ["subscribers"] });
      toast.success(`Recovery mode updated to ${mode}`);
    } catch {
      toast.error("Failed to update recovery mode. Please try again.");
    } finally {
      setIsSwitching(false);
    }
  };

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

      {account?.dpa_accepted && account.tier !== "free" && (
        <section className="mt-6 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-6">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Recovery Mode
          </h2>

          <div className="mt-4 space-y-3">
            {(["autopilot", "supervised"] as const).map((mode) => (
              <label
                key={mode}
                className={`flex cursor-pointer items-center gap-3 rounded-lg border p-4 transition-colors ${
                  account.engine_mode === mode
                    ? "border-[var(--accent-active)] bg-[var(--accent-active)]/5"
                    : "border-[var(--border)] hover:border-[var(--text-tertiary)]"
                }`}
              >
                <input
                  type="radio"
                  name="engine_mode"
                  value={mode}
                  checked={account.engine_mode === mode}
                  onChange={() => handleModeChange(mode)}
                  disabled={isSwitching}
                  className="accent-[var(--accent-active)]"
                />
                <div>
                  <span className="text-sm font-medium capitalize text-[var(--text-primary)]">
                    {mode}
                  </span>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {mode === "autopilot"
                      ? "SafeNet handles all recovery automatically — no action required from you."
                      : "SafeNet queues actions for your review before executing."}
                  </p>
                </div>
              </label>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
