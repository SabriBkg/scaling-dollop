"use client";

import { useAccount } from "@/hooks/useAccount";

export interface DpaGate {
  dpaAccepted: boolean;
  loading: boolean;
  sendDisabled: boolean;
  tooltip: string | undefined; // undefined when not disabled OR while loading — avoids flashing the AC5 "Sign the DPA" copy at users who have already signed
  activatePath: string;
}

export function useDpaGate(): DpaGate {
  const { data: account, isLoading } = useAccount();
  const loading = isLoading || account === undefined;
  const dpaAccepted = account?.dpa_accepted ?? false;
  // While loading we keep sendDisabled true (safer default — never enable a
  // gated control before we know the gate state) but suppress the tooltip so
  // already-signed users don't see "Sign the DPA" on first paint.
  const sendDisabled = loading || !dpaAccepted;
  const tooltip =
    !loading && !dpaAccepted ? "Sign the DPA to enable email sends" : undefined;
  return {
    dpaAccepted,
    loading,
    sendDisabled,
    tooltip,
    activatePath: "/activate",
  };
}
