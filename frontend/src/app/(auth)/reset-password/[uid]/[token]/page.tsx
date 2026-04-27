"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ROUTES } from "@/lib/constants";
import api from "@/lib/api";
import type { ApiError } from "@/types";

const RATE_LIMITED_MESSAGE =
  "Too many password reset requests. Try again later.";

export default function ResetPasswordPage() {
  const router = useRouter();
  const params = useParams<{ uid: string; token: string }>();
  const uid = (params.uid ?? "").trim();
  const token = (params.token ?? "").trim();
  const linkMissing = !uid || !token;
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [linkExpired, setLinkExpired] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});
    setGeneralError(null);
    setLinkExpired(false);
    setLoading(true);
    try {
      await api.post("/auth/password-reset/confirm/", {
        uid,
        token,
        new_password: password,
        new_password_confirm: passwordConfirm,
      });
      router.replace(`${ROUTES.LOGIN}?reset=success`);
    } catch (err: unknown) {
      const response = (err as { response?: { status?: number; data?: { error?: ApiError } } })
        ?.response;
      if (response?.status === 429) {
        setGeneralError(RATE_LIMITED_MESSAGE);
      } else {
        const apiErr = response?.data?.error;
        if (apiErr?.code === "INVALID_RESET_LINK") {
          setLinkExpired(true);
        } else if (apiErr?.code === "VALIDATION_ERROR" && apiErr.field) {
          setFieldErrors({ [apiErr.field]: apiErr.message });
        } else {
          setGeneralError(apiErr?.message ?? "Something went wrong. Please try again.");
        }
      }
    } finally {
      setLoading(false);
    }
  };

  if (linkMissing || linkExpired) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-bg-base">
        <div className="w-full max-w-sm px-6 py-12 text-center">
          <h1 className="mb-4 text-2xl font-bold text-text-primary">Link expired</h1>
          <p className="mb-6 text-text-secondary">
            This reset link is invalid or has expired. Please request a new one.
          </p>
          <Link href={ROUTES.FORGOT_PASSWORD} className="text-sm hover:underline">
            Request a new reset link
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-base">
      <div className="w-full max-w-sm px-6 py-12">
        <h1 className="mb-8 text-2xl font-bold text-center text-text-primary">
          Choose a new password
        </h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Input
              type="password"
              placeholder="New password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              aria-label="New password"
            />
            <p className="mt-1 text-xs text-text-tertiary">Minimum 8 characters</p>
            {fieldErrors.new_password && (
              <p className="mt-1 text-sm text-accent-fraud">{fieldErrors.new_password}</p>
            )}
          </div>
          <div>
            <Input
              type="password"
              placeholder="Confirm new password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
              autoComplete="new-password"
              aria-label="Confirm new password"
            />
            {fieldErrors.new_password_confirm && (
              <p className="mt-1 text-sm text-accent-fraud">{fieldErrors.new_password_confirm}</p>
            )}
          </div>
          {generalError && (
            <p className="text-sm text-accent-fraud" role="alert">
              {generalError}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Updating..." : "Update password"}
          </Button>
        </form>
      </div>
    </main>
  );
}
