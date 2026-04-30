"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { ApiResponse } from "@/types";
import type {
  FailedPayment,
  SortDirection,
  SortKey,
} from "@/types/failed_payment";

export function useFailedPayments(
  sort: SortKey = "date",
  dir: SortDirection = "desc"
) {
  return useQuery<FailedPayment[]>({
    queryKey: ["failed-payments", sort, dir],
    queryFn: async () => {
      const query = new URLSearchParams({ sort, dir }).toString();
      const { data } = await api.get<ApiResponse<FailedPayment[]>>(
        `/dashboard/failed-payments/?${query}`
      );
      return data.data;
    },
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}
