"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setTokens } from "@/lib/auth";
import { ROUTES } from "@/lib/constants";
import api from "@/lib/api";

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<"loading" | "error">("loading");

  useEffect(() => {
    const error = searchParams.get("error");
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (error) {
      router.replace(`${ROUTES.REGISTER}?error=stripe_denied`);
      return;
    }

    if (!code || !state) {
      router.replace(`${ROUTES.REGISTER}?error=missing_params`);
      return;
    }

    (async () => {
      try {
        const response = await api.post<{ data: { access: string; refresh: string; account_id: number } }>(
          "/stripe/callback/",
          { code, state }
        );
        const { access, refresh } = response.data.data;
        await setTokens(access, refresh);
        router.replace(ROUTES.DASHBOARD);
      } catch (err: unknown) {
        const message =
          (err as { response?: { data?: { error?: { code?: string } } } })
            ?.response?.data?.error?.code ?? "callback_failed";
        setStatus("error");
        router.replace(`${ROUTES.REGISTER}?error=${message}`);
      }
    })();
  }, [searchParams, router]);

  return (
    <>
      {status === "loading" && (
        <>
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-cta border-t-transparent mx-auto mb-4" />
          <p className="text-text-secondary">Connecting your Stripe account...</p>
        </>
      )}
    </>
  );
}

export default function StripeCallbackPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-base">
      <div className="text-center">
        <Suspense fallback={
          <>
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-cta border-t-transparent mx-auto mb-4" />
            <p className="text-text-secondary">Connecting your Stripe account...</p>
          </>
        }>
          <CallbackHandler />
        </Suspense>
      </div>
    </main>
  );
}
