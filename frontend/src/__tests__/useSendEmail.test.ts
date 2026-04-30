import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AxiosError, AxiosHeaders } from "axios";
import React from "react";
import { useSendEmail, SendEmailError } from "@/hooks/useSendEmail";

const mockPost = vi.fn();

vi.mock("@/lib/api", () => ({
  default: { post: (...args: unknown[]) => mockPost(...args) },
}));

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  return { wrapper, queryClient };
}

function makeAxiosError(status: number, body: unknown, headers: Record<string, string> = {}): AxiosError {
  const err = new AxiosError("Request failed");
  err.response = {
    status,
    statusText: "ERR",
    data: body,
    headers: new AxiosHeaders(headers),
    config: {} as never,
  };
  return err;
}

describe("useSendEmail", () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it("posts to the correct URL with snake_case body", async () => {
    mockPost.mockResolvedValue({ data: { data: { queued: true, email_type: "update_payment", failure_id: 42 } } });
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useSendEmail(), { wrapper });

    result.current.mutate({ subscriberId: 7, failureId: 42, emailType: "update_payment" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockPost).toHaveBeenCalledWith(
      "/subscribers/7/send-email/",
      { email_type: "update_payment", failure_id: 42 },
    );
  });

  it("invalidates ['failed-payments'] on success", async () => {
    mockPost.mockResolvedValue({ data: { data: { queued: true, email_type: "update_payment", failure_id: 1 } } });
    const { wrapper, queryClient } = makeWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useSendEmail(), { wrapper });

    result.current.mutate({ subscriberId: 1, failureId: 1, emailType: "update_payment" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["failed-payments"] });
  });

  it("wraps 429 axios error into SendEmailError with retryAfterSeconds", async () => {
    mockPost.mockRejectedValue(
      makeAxiosError(
        429,
        { error: { code: "RATE_LIMITED", message: "Too many email send requests.", field: null } },
        { "retry-after": "42" },
      ),
    );
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useSendEmail(), { wrapper });

    result.current.mutate({ subscriberId: 1, failureId: 1, emailType: "update_payment" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    const err = result.current.error;
    expect(err).toBeInstanceOf(SendEmailError);
    expect(err?.code).toBe("RATE_LIMITED");
    expect(err?.retryAfterSeconds).toBe(42);
    expect(err?.status).toBe(429);
  });

  it("wraps 422 OPT_OUT into SendEmailError", async () => {
    mockPost.mockRejectedValue(
      makeAxiosError(
        422,
        { error: { code: "OPT_OUT", message: "Subscriber has opted out of notifications.", field: null } },
      ),
    );
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useSendEmail(), { wrapper });

    result.current.mutate({ subscriberId: 1, failureId: 1, emailType: "update_payment" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.code).toBe("OPT_OUT");
    expect(result.current.error?.retryAfterSeconds).toBeNull();
  });

  it("wraps 403 DPA_REQUIRED into SendEmailError", async () => {
    mockPost.mockRejectedValue(
      makeAxiosError(
        403,
        { error: { code: "DPA_REQUIRED", message: "Sign the DPA to enable email sends.", field: null } },
      ),
    );
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useSendEmail(), { wrapper });

    result.current.mutate({ subscriberId: 1, failureId: 1, emailType: "update_payment" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.code).toBe("DPA_REQUIRED");
  });

  it("missing retry-after header parses as null", async () => {
    mockPost.mockRejectedValue(
      makeAxiosError(429, { error: { code: "RATE_LIMITED", message: "x", field: null } }),
    );
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useSendEmail(), { wrapper });

    result.current.mutate({ subscriberId: 1, failureId: 1, emailType: "update_payment" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.retryAfterSeconds).toBeNull();
  });

  it("non-numeric retry-after parses as null", async () => {
    mockPost.mockRejectedValue(
      makeAxiosError(
        429,
        { error: { code: "RATE_LIMITED", message: "x", field: null } },
        { "retry-after": "soon" },
      ),
    );
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useSendEmail(), { wrapper });

    result.current.mutate({ subscriberId: 1, failureId: 1, emailType: "update_payment" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.retryAfterSeconds).toBeNull();
  });
});
