"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { ApiResponse } from "@/types";
import type { SubscriberCard } from "@/types/subscriber";

export function useSubscribers() {
  return useQuery<SubscriberCard[]>({
    queryKey: ["subscribers"],
    queryFn: async () => {
      const { data } = await api.get<ApiResponse<SubscriberCard[]>>(
        "/subscribers/"
      );
      return data.data;
    },
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}
