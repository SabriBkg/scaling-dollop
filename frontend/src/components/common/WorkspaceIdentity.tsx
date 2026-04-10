"use client";

import { useAccount } from "@/hooks/useAccount";
import { Separator } from "@/components/ui/separator";

function Monogram({ name }: { name: string }) {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");

  return (
    <div className="flex h-7 w-7 items-center justify-center rounded bg-[var(--accent-active)] text-xs font-semibold text-white">
      {letters || "SN"}
    </div>
  );
}

export function WorkspaceIdentity() {
  const { data: account, isLoading } = useAccount();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2">
        <div className="h-4 w-16 animate-pulse rounded bg-[var(--sn-border)]" />
        <div className="h-7 w-7 animate-pulse rounded bg-[var(--sn-border)]" />
        <div className="h-3 w-24 animate-pulse rounded bg-[var(--sn-border)]" />
      </div>
    );
  }

  const ownerName = account?.owner
    ? `${account.owner.first_name} ${account.owner.last_name}`.trim()
    : "";
  const saasName = "SafeNet";

  return (
    <div className="flex items-center gap-2.5">
      <span className="text-sm font-semibold text-[var(--text-primary)]">
        {saasName}
      </span>
      <Separator orientation="vertical" className="h-5" />
      <Monogram name={ownerName || saasName} />
      <div className="hidden sm:flex sm:flex-col">
        <span className="text-xs font-medium leading-tight text-[var(--text-primary)]">
          {saasName}
        </span>
        <span className="text-[11px] leading-tight text-[var(--text-tertiary)]">
          {ownerName ? `${ownerName}'s workspace` : "Workspace"}
        </span>
      </div>
    </div>
  );
}
