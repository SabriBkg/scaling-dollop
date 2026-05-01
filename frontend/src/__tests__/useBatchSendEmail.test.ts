import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AxiosError, AxiosHeaders } from "axios";
import React from "react";
import { useBatchSendEmail } from "@/hooks/useBatchSendEmail";
import { SendEmailError } from "@/hooks/useSendEmail";

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

function makeAxiosError(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): AxiosError {
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

const happy = {
  queued: 3,
  failed: 0,
  failures: [],
  selections_total: 3,
};

const sample = [
  { subscriber_id: 1, failure_id: 10, email_type: "update_payment" as const },
  { subscriber_id: 2, failure_id: 20, email_type: "update_payment" as const },
  { subscriber_id: 3, failure_id: 30, email_type: "final_notice" as const },
];

describe("useBatchSendEmail", () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it("posts to /subscribers/batch-send-email/ with selections array", async () => {
    mockPost.mockResolvedValue({ data: { data: happy } });
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useBatchSendEmail(), { wrapper });

    result.current.mutate(sample);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockPost).toHaveBeenCalledWith(
      "/subscribers/batch-send-email/",
      { selections: sample },
    );
  });

  it("returns BatchSendResult on success", async () => {
    mockPost.mockResolvedValue({ data: { data: happy } });
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useBatchSendEmail(), { wrapper });

    result.current.mutate(sample);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(happy);
  });

  it("surfaces partial failures verbatim", async () => {
    const mixed = {
      queued: 1,
      failed: 1,
      failures: [
        { subscriber_id: 2, failure_id: 20, code: "OPT_OUT", message: "Subscriber has opted out of notifications." },
      ],
      selections_total: 2,
    };
    mockPost.mockResolvedValue({ data: { data: mixed } });
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useBatchSendEmail(), { wrapper });

    result.current.mutate(sample.slice(0, 2));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.failed).toBe(1);
    expect(result.current.data?.failures[0]).toEqual({
      subscriber_id: 2,
      failure_id: 20,
      code: "OPT_OUT",
      message: "Subscriber has opted out of notifications.",
    });
  });

  it("wraps 429 into SendEmailError with retryAfterSeconds", async () => {
    mockPost.mockRejectedValue(
      makeAxiosError(
        429,
        { error: { code: "RATE_LIMITED", message: "Too many batch send requests.", field: null } },
        { "retry-after": "42" },
      ),
    );
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useBatchSendEmail(), { wrapper });

    result.current.mutate(sample);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(SendEmailError);
    expect(result.current.error?.code).toBe("RATE_LIMITED");
    expect(result.current.error?.retryAfterSeconds).toBe(42);
  });

  it("wraps 403 DPA_REQUIRED into SendEmailError", async () => {
    mockPost.mockRejectedValue(
      makeAxiosError(
        403,
        { error: { code: "DPA_REQUIRED", message: "Sign the DPA to enable email sends.", field: null } },
      ),
    );
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useBatchSendEmail(), { wrapper });

    result.current.mutate(sample);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.code).toBe("DPA_REQUIRED");
  });

  it("invalidates failed-payments and dashboard summary on success", async () => {
    mockPost.mockResolvedValue({ data: { data: happy } });
    const { wrapper, queryClient } = makeWrapper();
    const spy = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useBatchSendEmail(), { wrapper });

    result.current.mutate(sample);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith({ queryKey: ["failed-payments"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["dashboard", "summary"] });
  });

  it("missing retry-after header parses as null", async () => {
    mockPost.mockRejectedValue(
      makeAxiosError(429, { error: { code: "RATE_LIMITED", message: "x", field: null } }),
    );
    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => useBatchSendEmail(), { wrapper });

    result.current.mutate(sample);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.retryAfterSeconds).toBeNull();
  });
});
