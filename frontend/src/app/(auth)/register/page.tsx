"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import axios from "axios";
import { ConnectStripe } from "@/components/onboarding/ConnectStripe";
import { ROUTES } from "@/lib/constants";

const ERROR_MESSAGES: Record<string, string> = {
  stripe_denied: "You declined the Stripe connection. Please try again to connect your account.",
  callback_failed: "Something went wrong during connection. Please try again.",
  missing_params: "The connection link was incomplete. Please try connecting again.",
  INVALID_STATE: "Your session expired. Please try connecting again.",
  STRIPE_AUTH_FAILED: "Stripe couldn't verify your authorization. Please try again.",
  token_storage_failed: "Failed to save your session. Please try again.",
  EMAIL_EXISTS: "An account with this email already exists. Please sign in instead.",
};

function RegisterContent() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");

  const errorMessage = error ? (ERROR_MESSAGES[error] ?? "An error occurred. Please try again.") : null;

  return (
    <>
      {errorMessage && (
        <div className="mb-6 rounded-md border border-accent-fraud/30 bg-accent-fraud/10 px-4 py-3 text-sm text-accent-fraud">
          {errorMessage}
        </div>
      )}

      <ConnectStripe />
    </>
  );
}

export default function RegisterPage() {
  const router = useRouter();

  useEffect(() => {
    (async () => {
      try {
        // Use plain axios to avoid the 401 interceptor redirecting to /login
        const res = await axios.get(`${process.env.NEXT_PUBLIC_API_URL}/account/me/`, {
          withCredentials: true,
        });
        if (res.status === 200) {
          router.replace(ROUTES.DASHBOARD);
        }
      } catch {
        // Not authenticated — stay on register page
      }
    })();
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-base">
      <div className="w-full max-w-md px-6 py-12 text-center">
        <h1 className="mb-2 text-3xl font-bold text-text-primary">SafeNet</h1>
        <p className="mb-8 text-text-secondary">
          Automated payment failure recovery for Stripe subscriptions.
        </p>

        <Suspense>
          <RegisterContent />
        </Suspense>

        <p className="mt-6 text-xs text-text-tertiary">
          Already have an account?{" "}
          <a href={ROUTES.LOGIN} className="text-cta hover:underline">
            Sign in
          </a>
        </p>
      </div>
    </main>
  );
}
