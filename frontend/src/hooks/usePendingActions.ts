"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { PendingAction } from "@/types/actions";

interface PendingActionsResponse {
  data: PendingAction[];
  meta: { total: number };
}

export function usePendingActions() {
  return useQuery<PendingAction[]>({
    queryKey: ["actions", "pending"],
    queryFn: async () => {
      const { data } = await api.get<PendingActionsResponse>(
        "/actions/pending/"
      );
      return data.data;
    },
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}
