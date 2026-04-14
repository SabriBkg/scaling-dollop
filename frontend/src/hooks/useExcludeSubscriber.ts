"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

interface ExcludeResult {
  excluded: boolean;
  subscriber_id: number;
}

export function useExcludeSubscriber() {
  const queryClient = useQueryClient();

  return useMutation<ExcludeResult, Error, number>({
    mutationFn: async (subscriberId) => {
      const { data } = await api.post<{ data: ExcludeResult }>(
        `/subscribers/${subscriberId}/exclude/`
      );
      return data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions", "pending"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
    },
  });
}
