"use client";

import { useState } from "react";
import Link from "next/link";
import { ROUTES } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";

const GENERIC_CONFIRMATION =
  "If an account exists for that email, we've sent a reset link.";
const RATE_LIMITED_MESSAGE =
  "Too many password reset requests. Try again later.";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [message, setMessage] = useState<string>(GENERIC_CONFIRMATION);
  const [rateLimited, setRateLimited] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setRateLimited(false);
    try {
      const res = await api.post("/auth/password-reset/", { email });
      setMessage(res.data?.data?.message ?? GENERIC_CONFIRMATION);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 429) {
        setRateLimited(true);
        setMessage(RATE_LIMITED_MESSAGE);
      } else {
        // Render the same generic confirmation regardless — the backend hides
        // whether the email is registered, and we mirror that on the client.
        setMessage(GENERIC_CONFIRMATION);
      }
    } finally {
      setLoading(false);
      setSubmitted(true);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-base">
      <div className="w-full max-w-sm px-6 py-12">
        <h1 className="mb-8 text-2xl font-bold text-center text-text-primary">
          Reset your password
        </h1>

        {submitted ? (
          <p
            className={`rounded-md border px-4 py-3 text-sm ${
              rateLimited
                ? "border-accent-fraud bg-bg-elevated text-accent-fraud"
                : "border-border-default bg-bg-elevated text-text-secondary"
            }`}
            role={rateLimited ? "alert" : "status"}
          >
            {message}
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm text-text-secondary">
              Enter your email and we&apos;ll send you a link to reset your password.
            </p>
            <Input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              aria-label="Email address"
            />
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Sending..." : "Send reset link"}
            </Button>
          </form>
        )}

        <p className="mt-6 text-center text-xs text-text-tertiary">
          <Link href={ROUTES.LOGIN} className="hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
