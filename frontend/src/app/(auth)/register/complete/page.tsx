"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ROUTES } from "@/lib/constants";
import api from "@/lib/api";
import { useAccount } from "@/hooks/useAccount";
import type { ApiError } from "@/types";

export default function CompleteProfilePage() {
  const router = useRouter();
  const { data: account, isLoading: accountLoading } = useAccount();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Guard: redirect to dashboard if profile is already complete,
  // or to login if the user is not authenticated (useAccount 401 clears tokens).
  useEffect(() => {
    if (accountLoading) return;
    if (account?.profile_complete) {
      router.replace(ROUTES.DASHBOARD);
    }
  }, [account, accountLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});
    setGeneralError(null);
    setLoading(true);

    try {
      await api.post("/account/complete-profile/", {
        first_name: firstName,
        last_name: lastName,
        company_name: companyName,
        password,
        password_confirm: passwordConfirm,
      });

      router.replace(ROUTES.DASHBOARD);
    } catch (err: unknown) {
      const apiErr = (err as { response?: { data?: ApiError } })?.response
        ?.data?.error;
      if (apiErr?.field) {
        setFieldErrors({ [apiErr.field]: apiErr.message });
      } else if (apiErr?.message) {
        setGeneralError(apiErr.message);
      } else {
        setGeneralError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  // Show nothing while checking account status
  if (accountLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg-base">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-cta border-t-transparent" />
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-base">
      <div className="w-full max-w-[480px] px-6 py-12">
        <h1 className="mb-2 text-2xl font-bold text-center text-text-primary">
          SafeNet
        </h1>
        <p className="mb-8 text-center text-text-secondary">
          Almost there — tell us about you and your product.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Input
              type="text"
              placeholder="First name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
              autoComplete="given-name"
              aria-label="First name"
            />
            {fieldErrors.first_name && (
              <p className="mt-1 text-sm text-accent-fraud">{fieldErrors.first_name}</p>
            )}
          </div>

          <div>
            <Input
              type="text"
              placeholder="Last name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
              autoComplete="family-name"
              aria-label="Last name"
            />
            {fieldErrors.last_name && (
              <p className="mt-1 text-sm text-accent-fraud">{fieldErrors.last_name}</p>
            )}
          </div>

          <div>
            <Input
              type="text"
              placeholder="Company / SaaS name (e.g., ProductivityPro)"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              required
              autoComplete="organization"
              aria-label="Company or SaaS name"
            />
            {fieldErrors.company_name && (
              <p className="mt-1 text-sm text-accent-fraud">{fieldErrors.company_name}</p>
            )}
          </div>

          <div>
            <Input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              aria-label="Password"
            />
            <p className="mt-1 text-xs text-text-tertiary">Minimum 8 characters</p>
            {fieldErrors.password && (
              <p className="mt-1 text-sm text-accent-fraud">{fieldErrors.password}</p>
            )}
          </div>

          <div>
            <Input
              type="password"
              placeholder="Confirm password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
              autoComplete="new-password"
              aria-label="Confirm password"
            />
            {fieldErrors.password_confirm && (
              <p className="mt-1 text-sm text-accent-fraud">{fieldErrors.password_confirm}</p>
            )}
          </div>

          {generalError && (
            <p className="text-sm text-accent-fraud" role="alert">
              {generalError}
            </p>
          )}

          <Button type="submit" className="w-full bg-cta hover:bg-cta/90" disabled={loading}>
            {loading ? "Setting up..." : "Complete Setup"}
          </Button>
        </form>
      </div>
    </main>
  );
}
