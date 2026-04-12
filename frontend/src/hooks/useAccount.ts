"use client";

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import type { Account, ApiResponse } from "@/types";

export function useAccount() {
  return useQuery<Account>({
    queryKey: ["account", "me"],
    queryFn: async () => {
      const { data } = await api.get<ApiResponse<Account>>(
        "/account/me/"
      );
      return data.data;
    },
    staleTime: 5 * 60 * 1000,
  });
}
