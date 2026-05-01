"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import api from "@/lib/api";
import {
  SendEmailError,
  type SendEmailErrorEnvelope,
  type SendableEmailType,
} from "@/hooks/useSendEmail";

export interface BatchSelection {
  subscriber_id: number;
  failure_id: number;
  email_type: SendableEmailType;
}

export interface BatchSendFailure {
  subscriber_id: number;
  failure_id: number;
  code: string;
  message: string;
}

export interface BatchSendResult {
  queued: number;
  failed: number;
  failures: BatchSendFailure[];
  selections_total: number;
}

export function useBatchSendEmail() {
  const queryClient = useQueryClient();
  return useMutation<BatchSendResult, SendEmailError, BatchSelection[]>({
    mutationFn: async (selections) => {
      try {
        const { data } = await api.post<{ data: BatchSendResult }>(
          "/subscribers/batch-send-email/",
          { selections },
        );
        return data.data;
      } catch (err) {
        if (err instanceof AxiosError && err.response) {
          const envelope = (err.response.data?.error ?? {
            code: "UNKNOWN",
            message: "Request failed.",
            field: null,
          }) as SendEmailErrorEnvelope;
          const retryAfter = err.response.headers?.["retry-after"] ?? null;
          throw new SendEmailError(envelope, err.response.status, retryAfter);
        }
        throw err;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["failed-payments"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
    },
  });
}
