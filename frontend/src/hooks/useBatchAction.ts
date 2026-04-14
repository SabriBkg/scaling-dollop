"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import type { BatchResult } from "@/types/actions";

export function useBatchAction() {
  const queryClient = useQueryClient();

  return useMutation<BatchResult, Error, number[]>({
    mutationFn: async (actionIds) => {
      const { data } = await api.post<{ data: BatchResult }>(
        "/actions/batch/",
        { action_ids: actionIds }
      );
      return data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions", "pending"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
    },
  });
}
