"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { useAccount } from "@/hooks/useAccount";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Shield } from "lucide-react";
import api from "@/lib/api";
import type { Account, ApiResponse } from "@/types";

export default function DpaAcceptancePage() {
  const router = useRouter();
  const { data: account, isLoading: accountLoading } = useAccount();
  const queryClient = useQueryClient();
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!accountLoading && account) {
      if (account.tier === "free") {
        router.replace("/dashboard");
      } else if (account.dpa_accepted && account.engine_mode) {
        router.replace("/dashboard");
      } else if (account.dpa_accepted) {
        router.replace("/activate/mode");
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

  const handleAccept = async () => {
    setIsSubmitting(true);
    try {
      const { data } = await api.post<ApiResponse<Account>>("/account/dpa/accept/");
      queryClient.setQueryData(["account", "me"], data.data);
      router.push("/activate/mode");
    } catch {
      toast.error("Failed to accept the Data Processing Agreement. Please try again.");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl py-8">
      <div className="mb-8 flex items-center gap-3">
        <Shield className="h-8 w-8 text-[var(--accent-active)]" />
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
          Data Processing Agreement
        </h1>
      </div>

      <div className="space-y-6 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-8">
        <section>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            What SafeNet Processes
          </h2>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            SafeNet processes failed payment transaction data from your Stripe account,
            including decline codes, payment amounts, customer identifiers, and card
            metadata. This data is used exclusively to recover failed payments on your behalf.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            On Whose Behalf
          </h2>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            SafeNet acts as a data processor on behalf of your business ({account.company_name || "your company"}).
            You remain the data controller. SafeNet processes data solely under your
            instructions as defined by this agreement.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Purpose of Processing
          </h2>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            Data is processed for the sole purpose of identifying recoverable failed payments,
            executing recovery strategies (retries, customer notifications), and reporting
            recovery outcomes to you. No data is used for marketing, profiling, or any
            purpose beyond payment recovery.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Retention Policy
          </h2>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            Transaction data is retained for 90 days from the date of ingestion. After the
            retention period, data is permanently deleted. Aggregated, anonymized analytics
            may be retained for service improvement but contain no personally identifiable
            information.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Security Measures
          </h2>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            All Stripe API tokens are encrypted at rest using Fernet symmetric encryption.
            Data in transit is protected by TLS 1.2+. Access to production systems is
            restricted to authorized personnel only. Audit logs record all data access
            and processing events.
          </p>
        </section>
      </div>

      <div className="mt-8 flex items-center justify-between">
        <button
          onClick={() => router.push("/dashboard")}
          className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          Go back to dashboard
        </button>

        <button
          onClick={handleAccept}
          disabled={isSubmitting}
          className="rounded-lg bg-[var(--cta)] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[var(--cta-hover)] focus:outline-2 focus:outline-offset-2 focus:outline-[var(--accent-active)] disabled:opacity-50"
        >
          {isSubmitting ? "Processing…" : "I accept and sign"}
        </button>
      </div>
    </div>
  );
}
