"use client";

import Link from "next/link";
import { useAccount } from "@/hooks/useAccount";

export function ActivateEngineCTA() {
  const { data: account } = useAccount();

  if (!account || account.tier === "free" || account.engine_active) {
    return null;
  }

  return (
    <div className="rounded-lg border border-[var(--accent-active)]/30 bg-[var(--accent-active)]/5 px-4 py-3">
      <p className="text-sm text-[var(--text-secondary)]">
        Your recovery engine is ready to activate.
      </p>
      <Link
        href={account.dpa_accepted ? "/activate/mode" : "/activate"}
        className="mt-2 inline-block rounded-lg bg-[var(--cta)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--cta-hover)]"
      >
        {account.dpa_accepted ? "Select recovery mode" : "Activate recovery engine"}
      </Link>
    </div>
  );
}
