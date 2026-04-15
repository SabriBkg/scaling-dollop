"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { useAccount } from "@/hooks/useAccount";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Zap, Eye } from "lucide-react";
import api from "@/lib/api";
import type { Account, ApiResponse } from "@/types";

type EngineMode = "autopilot" | "supervised";

export default function ModeSelectionPage() {
  const router = useRouter();
  const { data: account, isLoading: accountLoading } = useAccount();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<EngineMode | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!accountLoading && account) {
      if (!account.dpa_accepted) {
        router.replace("/activate");
      } else if (account.engine_mode) {
        router.replace("/dashboard");
      }
    }
  }, [account, accountLoading, router]);

  if (accountLoading || !account) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--accent-active)] border-t-transparent" />
      </div>
    );
  }

  const handleConfirm = async () => {
    if (!selected) return;
    setIsSubmitting(true);
    try {
      const { data } = await api.post<ApiResponse<Account>>("/account/engine/mode/", {
        mode: selected,
      });
      queryClient.setQueryData(["account", "me"], data.data);
      queryClient.invalidateQueries({ queryKey: ["account", "me"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      queryClient.invalidateQueries({ queryKey: ["actions", "pending"] });
      queryClient.invalidateQueries({ queryKey: ["subscribers"] });
      router.push("/dashboard");
    } catch {
      toast.error("Failed to activate the recovery engine. Please try again.");
      setIsSubmitting(false);
    }
  };

  const modes: Array<{
    value: EngineMode;
    icon: typeof Zap;
    title: string;
    description: string;
    consequence: string;
  }> = [
    {
      value: "autopilot",
      icon: Zap,
      title: "Autopilot",
      description:
        "SafeNet handles all recovery automatically — no action required from you.",
      consequence:
        "Failed payments are retried and customers notified automatically based on best-practice rules. You can review results anytime on your dashboard.",
    },
    {
      value: "supervised",
      icon: Eye,
      title: "Supervised",
      description:
        "SafeNet queues actions for your review before executing.",
      consequence:
        "Recovery actions are proposed but not executed until you approve them. Review and approve actions in the Review Queue.",
    },
  ];

  return (
    <div className="mx-auto max-w-2xl py-8">
      <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
        Choose your recovery mode
      </h1>
      <p className="mt-2 text-sm text-[var(--text-secondary)]">
        Select how SafeNet should handle failed payment recovery. You can change this
        anytime in Settings.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {modes.map((mode) => {
          const Icon = mode.icon;
          const isSelected = selected === mode.value;

          return (
            <button
              key={mode.value}
              onClick={() => setSelected(mode.value)}
              className={`flex flex-col items-start rounded-lg border-2 p-6 text-left transition-all ${
                isSelected
                  ? "border-[var(--accent-active)] bg-[var(--surface-raised)]"
                  : "border-[var(--border)] bg-[var(--surface-raised)] hover:border-[var(--text-tertiary)]"
              }`}
            >
              <Icon
                className={`h-6 w-6 ${
                  isSelected ? "text-[var(--accent-active)]" : "text-[var(--text-secondary)]"
                }`}
              />
              <h2 className="mt-3 text-lg font-semibold text-[var(--text-primary)]">
                {mode.title}
              </h2>
              <p className="mt-1 text-sm font-medium text-[var(--text-secondary)]">
                {mode.description}
              </p>
              <p className="mt-3 text-xs text-[var(--text-tertiary)]">
                {mode.consequence}
              </p>
            </button>
          );
        })}
      </div>

      <div className="mt-8 flex justify-end">
        <button
          onClick={handleConfirm}
          disabled={!selected || isSubmitting}
          className="rounded-lg bg-[var(--cta)] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[var(--cta-hover)] focus:outline-2 focus:outline-offset-2 focus:outline-[var(--accent-active)] disabled:opacity-50"
        >
          {isSubmitting ? "Activating…" : "Confirm and activate"}
        </button>
      </div>
    </div>
  );
}
