"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import type { PendingAction } from "@/types/actions";

interface PendingActionRowProps {
  action: PendingAction;
  selected: boolean;
  onToggle: (id: number) => void;
}

const ACTION_LABELS: Record<string, string> = {
  retry_notify: "Retry + Notify",
  notify_only: "Notify Only",
  no_action: "No Action",
};

function formatCents(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

export function PendingActionRow({
  action,
  selected,
  onToggle,
}: PendingActionRowProps) {
  return (
    <tr className="border-b border-[var(--sn-border)]">
      <td className="px-4 py-3">
        <Checkbox
          checked={selected}
          onCheckedChange={() => onToggle(action.id)}
          aria-label={`Select ${action.subscriber_name}`}
        />
      </td>
      <td className="px-4 py-3 text-sm">{action.subscriber_name}</td>
      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
        {action.decline_reason}
      </td>
      <td className="px-4 py-3">
        <Badge variant="outline">
          {ACTION_LABELS[action.recommended_action] ?? action.recommended_action}
        </Badge>
      </td>
      <td className="px-4 py-3 text-sm font-medium tabular-nums">
        {formatCents(action.amount_cents)}
      </td>
    </tr>
  );
}
