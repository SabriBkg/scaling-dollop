"use client";

import { useState } from "react";
import { useAccount } from "@/hooks/useAccount";
import { useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export function UpgradeCTA() {
  const { data: account } = useAccount();
  const queryClient = useQueryClient();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!account || account.tier !== "free") {
    return null;
  }

  const handleUpgrade = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const { data } = await api.post<{ data: { checkout_url: string } }>(
        "/billing/checkout/"
      );
      window.location.href = data.data.checkout_url;
    } catch {
      setError("Failed to start checkout. Please try again.");
      setIsLoading(false);
    }
  };

  return (
    <div className="mt-3">
      <button
        onClick={handleUpgrade}
        disabled={isLoading}
        className="w-full rounded-lg bg-[var(--cta)] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[var(--cta-hover)] focus:outline-2 focus:outline-offset-2 focus:outline-[var(--accent-active)] disabled:opacity-50"
      >
        {isLoading ? "Redirecting…" : "Activate recovery engine — €29/month"}
      </button>
      {error && (
        <p className="mt-1 text-xs text-red-500">{error}</p>
      )}
    </div>
  );
}
