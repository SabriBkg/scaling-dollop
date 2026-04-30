"use client";

import Link from "next/link";
import { useAccount } from "@/hooks/useAccount";

export function ActivateEngineCTA() {
  const { data: account } = useAccount();

  // v1: DPA acceptance is the sole activation step. Once signed, there is no
  // "select recovery mode" step — the dashboard exposes per-row send actions
  // directly. Hide the CTA for DPA-accepted accounts to avoid bouncing the
  // user through the /activate/mode redirect stub.
  if (
    !account ||
    account.tier === "free" ||
    account.engine_active ||
    account.dpa_accepted
  ) {
    return null;
  }

  return (
    <div className="rounded-lg border border-[var(--accent-active)]/30 bg-[var(--accent-active)]/5 px-4 py-3">
      <p className="text-sm text-[var(--text-secondary)]">
        Sign the Data Processing Agreement to enable email sends.
      </p>
      <Link
        href="/activate"
        className="mt-2 inline-block rounded-lg bg-[var(--cta)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--cta-hover)]"
      >
        Sign the Data Processing Agreement
      </Link>
    </div>
  );
}
