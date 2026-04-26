"use client";

import { useQuery } from "@tanstack/react-query";

import api from "@/lib/api";
import type { ApiResponse, NotificationTone } from "@/types";

export interface NotificationPreviewData {
  tone: NotificationTone;
  subject: string;
  html_body: string;
  sample_subscriber_email: string;
  sample_decline_code: string;
}

export function useNotificationPreview(tone: NotificationTone) {
  return useQuery<NotificationPreviewData>({
    queryKey: ["notification-preview", tone],
    queryFn: async () => {
      const { data } = await api.get<ApiResponse<NotificationPreviewData>>(
        `/account/notification-preview/?tone=${encodeURIComponent(tone)}`,
      );
      return data.data;
    },
    staleTime: 5 * 60 * 1000,
  });
}
