"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import api from "@/lib/api";
import type { RecommendedEmailType } from "@/types/failed_payment";

export type SendableEmailType = Exclude<RecommendedEmailType, null>;

export interface SendEmailVariables {
  subscriberId: number;
  failureId: number;
  emailType: SendableEmailType;
}

interface SendEmailResult {
  queued: boolean;
  email_type: SendableEmailType;
  failure_id: number;
}

export interface SendEmailErrorEnvelope {
  code: string;
  message: string;
  field: string | null;
}

export class SendEmailError extends Error {
  readonly code: string;
  readonly field: string | null;
  readonly status: number;
  readonly retryAfterSeconds: number | null;
  constructor(envelope: SendEmailErrorEnvelope, status: number, retryAfter: string | null) {
    super(envelope.message);
    this.code = envelope.code;
    this.field = envelope.field;
    this.status = status;
    const parsed = retryAfter ? parseInt(retryAfter, 10) : NaN;
    this.retryAfterSeconds = Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }
}

export function useSendEmail() {
  const queryClient = useQueryClient();
  return useMutation<SendEmailResult, SendEmailError, SendEmailVariables>({
    mutationFn: async ({ subscriberId, failureId, emailType }) => {
      try {
        const { data } = await api.post<{ data: SendEmailResult }>(
          `/subscribers/${subscriberId}/send-email/`,
          { email_type: emailType, failure_id: failureId },
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
