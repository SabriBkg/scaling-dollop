"use client";

import { useAccount } from "@/hooks/useAccount";

export function UpgradeCTA() {
  const { data: account } = useAccount();

  if (!account || account.tier !== "free") {
    return null;
  }

  return (
    <div className="mt-3">
      <button
        className="w-full rounded-lg bg-[var(--cta)] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[var(--cta-hover)] focus:outline-2 focus:outline-offset-2 focus:outline-[var(--accent-active)]"
      >
        Activate recovery engine &mdash; &euro;29/month
      </button>
    </div>
  );
}
