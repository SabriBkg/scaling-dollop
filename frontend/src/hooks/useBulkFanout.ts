"use client";

import { useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

type Endpoint = "mark-resolved" | "exclude";

export interface BulkFanoutFailure {
  subscriber_id: number;
  code: string | null;
  status: number | null;
  reason: string;
}

export interface BulkFanoutResult {
  succeeded: number;
  failed: number;
  total: number;
  failures: BulkFanoutFailure[];
}

export function useBulkFanout(endpoint: Endpoint) {
  const queryClient = useQueryClient();
  const [isPending, setIsPending] = useState(false);
  const [lastResult, setLastResult] = useState<BulkFanoutResult | null>(null);

  const run = useCallback(
    async (subscriberIds: number[]): Promise<BulkFanoutResult> => {
      setIsPending(true);
      const settled = await Promise.allSettled(
        subscriberIds.map((id) =>
          api.post(`/subscribers/${id}/${endpoint}/`).then(() => id),
        ),
      );
      const failures: BulkFanoutFailure[] = [];
      let succeeded = 0;
      settled.forEach((res, i) => {
        if (res.status === "fulfilled") {
          succeeded += 1;
        } else {
          const err = res.reason as {
            response?: {
              status?: number;
              data?: { error?: { code?: string; message?: string } };
            };
          };
          failures.push({
            subscriber_id: subscriberIds[i],
            code: err?.response?.data?.error?.code ?? null,
            status: err?.response?.status ?? null,
            reason: err?.response?.data?.error?.message ?? "Request failed.",
          });
        }
      });
      const result: BulkFanoutResult = {
        succeeded,
        failed: failures.length,
        total: subscriberIds.length,
        failures,
      };
      setLastResult(result);
      queryClient.invalidateQueries({ queryKey: ["failed-payments"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      setIsPending(false);
      return result;
    },
    [endpoint, queryClient],
  );

  return { run, isPending, lastResult };
}
