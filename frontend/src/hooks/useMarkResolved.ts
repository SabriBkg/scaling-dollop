"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

interface MarkResolvedResult {
  resolved: boolean;
  subscriber_id: number;
  from_status: string;
  to_status: "recovered";
}

export function useMarkResolved() {
  const queryClient = useQueryClient();
  return useMutation<MarkResolvedResult, Error, number>({
    mutationFn: async (subscriberId) => {
      const { data } = await api.post<{ data: MarkResolvedResult }>(
        `/subscribers/${subscriberId}/mark-resolved/`,
      );
      return data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["failed-payments"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
    },
  });
}
