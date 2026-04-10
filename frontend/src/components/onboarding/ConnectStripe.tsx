"use client";

import { useStripeConnect } from "@/hooks/useStripeConnect";
import { Button } from "@/components/ui/button";

export function ConnectStripe() {
  const { initiateConnect, loading, error } = useStripeConnect();

  return (
    <div className="flex flex-col items-center gap-4">
      <Button
        onClick={initiateConnect}
        disabled={loading}
        size="lg"
        className="w-full max-w-xs bg-cta text-white hover:bg-cta-hover"
        aria-label="Connect your Stripe account to SafeNet"
      >
        {loading ? (
          <>
            <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            Connecting...
          </>
        ) : (
          "Connect with Stripe"
        )}
      </Button>

      {error && (
        <p className="text-sm text-accent-fraud" role="alert">
          {error}
        </p>
      )}

      <p className="text-xs text-text-tertiary">
        No API keys needed — SafeNet uses Stripe&apos;s official OAuth.
      </p>
    </div>
  );
}
