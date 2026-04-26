"use client";

import { Button } from "@/components/ui/button";

interface BatchActionToolbarProps {
  selectedCount: number;
  onApprove: () => void;
  onExclude: () => void;
  onDeselectAll: () => void;
  isApproving: boolean;
}

export function BatchActionToolbar({
  selectedCount,
  onApprove,
  onExclude,
  onDeselectAll,
  isApproving,
}: BatchActionToolbarProps) {
  if (selectedCount === 0) return null;

  return (
    <div
      role="toolbar"
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-[var(--sn-border)] bg-[var(--bg-surface)] px-4 py-3 shadow-lg"
    >
      <div className="mx-auto flex max-w-[1280px] items-center justify-between">
        <span className="text-sm text-[var(--text-secondary)]">
          {selectedCount} action{selectedCount !== 1 ? "s" : ""} selected
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={onDeselectAll}
            className="text-sm text-[var(--text-secondary)] underline hover:text-[var(--text-primary)]"
          >
            Deselect all
          </button>
          <Button variant="outline" size="sm" onClick={onExclude}>
            Exclude from automation
          </Button>
          <Button size="sm" onClick={onApprove} disabled={isApproving}>
            {isApproving ? "Applying…" : "Apply recommended actions"}
          </Button>
        </div>
      </div>
    </div>
  );
}
