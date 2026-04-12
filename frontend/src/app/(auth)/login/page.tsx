"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { setTokens } from "@/lib/auth";
import { ROUTES } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConnectStripe } from "@/components/onboarding/ConnectStripe";
import api from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await api.post("/auth/token/", {
        username: email,
        password,
      });

      const { access, refresh, profile_complete } = response.data;
      await setTokens(access, refresh);
      router.replace(profile_complete === false ? ROUTES.REGISTER_COMPLETE : ROUTES.DASHBOARD);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
      setError(detail ?? "Invalid email or password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-base">
      <div className="w-full max-w-sm px-6 py-12">
        <h1 className="mb-8 text-2xl font-bold text-center text-text-primary">Sign in to SafeNet</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            aria-label="Email address"
          />
          <div>
            <Input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              aria-label="Password"
            />
            <p className="mt-1 text-right text-xs text-text-tertiary">
              <span className="cursor-not-allowed opacity-50">Forgot password?</span>
            </p>
          </div>

          {error && (
            <p className="text-sm text-accent-fraud" role="alert">
              {error}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </Button>
        </form>

        <div className="my-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-border-default" />
          <span className="text-xs text-text-tertiary">or</span>
          <div className="h-px flex-1 bg-border-default" />
        </div>

        <ConnectStripe />

        <p className="mt-6 text-center text-xs text-text-tertiary">
          New to SafeNet? Connect your Stripe account to get started.
        </p>
      </div>
    </main>
  );
}
