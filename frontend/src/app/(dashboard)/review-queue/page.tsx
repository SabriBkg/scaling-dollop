"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { usePendingActions } from "@/hooks/usePendingActions";
import { useBatchAction } from "@/hooks/useBatchAction";
import { useExcludeSubscriber } from "@/hooks/useExcludeSubscriber";
import { PendingActionRow } from "@/components/review/PendingActionRow";
import { BatchActionToolbar } from "@/components/review/BatchActionToolbar";
import { ExclusionDialog } from "@/components/review/ExclusionDialog";

export default function ReviewQueuePage() {
  const { data: actions, isLoading } = usePendingActions();
  const batchMutation = useBatchAction();
  const excludeMutation = useExcludeSubscriber();

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [exclusionDialogOpen, setExclusionDialogOpen] = useState(false);

  // Pre-select all rows on load
  useEffect(() => {
    if (actions && actions.length > 0) {
      setSelected(new Set(actions.map((a) => a.id)));
    }
  }, [actions]);

  const toggleSelection = useCallback((id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleApprove = useCallback(() => {
    const ids = Array.from(selected);
    batchMutation.mutate(ids, {
      onSuccess: (result) => {
        if (result.failed > 0 && result.approved > 0) {
          toast.warning(
            `${result.approved} actions queued, ${result.failed} failed`,
            { duration: 6000 }
          );
        } else if (result.failed > 0) {
          toast.error(`All ${result.failed} actions failed`, {
            duration: Infinity,
          });
        } else {
          toast.success(`${result.approved} actions queued`);
        }
        setSelected(new Set());
      },
      onError: () => {
        toast.error("Failed to process batch actions", {
          duration: Infinity,
        });
      },
    });
  }, [selected, batchMutation]);

  const handleExclude = useCallback(() => {
    if (!actions) return;
    // Get unique subscriber IDs from selected actions
    const subscriberIds = new Set(
      actions
        .filter((a) => selected.has(a.id))
        .map((a) => a.subscriber_id)
    );

    // Exclude each unique subscriber
    subscriberIds.forEach((subId) => {
      excludeMutation.mutate(subId, {
        onSuccess: () => {
          toast.success("Subscriber excluded from automation");
          setSelected(new Set());
        },
      });
    });
    setExclusionDialogOpen(false);
  }, [actions, selected, excludeMutation]);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-xl font-semibold">Review Queue</h1>
        <div className="animate-pulse space-y-3">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-12 rounded bg-[var(--bg-surface)]"
            />
          ))}
        </div>
      </div>
    );
  }

  if (!actions || actions.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-xl font-semibold">Review Queue</h1>
        <div className="rounded-lg border border-[var(--sn-border)] bg-[var(--bg-surface)] p-8 text-center">
          <p className="text-[var(--text-secondary)]">
            Nothing needs your eyes right now. Approved items and automated
            recoveries are handled.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 pb-20">
      <h1 className="text-xl font-semibold">Review Queue</h1>
      <div className="overflow-x-auto rounded-lg border border-[var(--sn-border)]">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[var(--sn-border)] bg-[var(--bg-surface)]">
              <th className="w-10 px-4 py-2" />
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-[var(--text-secondary)]">
                Subscriber
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-[var(--text-secondary)]">
                Decline Reason
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-[var(--text-secondary)]">
                Action
              </th>
              <th className="px-4 py-2 text-left text-xs font-medium uppercase text-[var(--text-secondary)]">
                Amount
              </th>
            </tr>
          </thead>
          <tbody>
            {actions.map((action) => (
              <PendingActionRow
                key={action.id}
                action={action}
                selected={selected.has(action.id)}
                onToggle={toggleSelection}
              />
            ))}
          </tbody>
        </table>
      </div>

      <BatchActionToolbar
        selectedCount={selected.size}
        onApprove={handleApprove}
        onExclude={() => setExclusionDialogOpen(true)}
        onDeselectAll={() => setSelected(new Set())}
        isApproving={batchMutation.isPending}
      />

      <ExclusionDialog
        open={exclusionDialogOpen}
        onOpenChange={setExclusionDialogOpen}
        onConfirm={handleExclude}
        isPending={excludeMutation.isPending}
      />
    </div>
  );
}
