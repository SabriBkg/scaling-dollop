"use client";

import { useState } from "react";
import { ChevronDownIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { FailedPayment } from "@/types/failed_payment";
import type { BatchSelection } from "@/hooks/useBatchSendEmail";
import type { SendableEmailType } from "@/hooks/useSendEmail";

const SPECIFIC_OPTIONS: Array<{ type: SendableEmailType; label: string }> = [
  { type: "update_payment", label: "Update payment" },
  { type: "retry_reminder", label: "Retry reminder" },
  { type: "final_notice", label: "Final notice" },
];

const EMAIL_TYPE_LABELS: Record<SendableEmailType, string> = {
  update_payment: "Update Payment",
  retry_reminder: "Retry Reminder",
  final_notice: "Final Notice",
};

type DialogPayload =
  | {
      kind: "send_recommended";
      selections: BatchSelection[];
      eligibleRows: FailedPayment[];
      skippedNoRecommendation: FailedPayment[];
      skippedNotEligible: FailedPayment[];
    }
  | {
      kind: "send_specific";
      selections: BatchSelection[];
      eligibleRows: FailedPayment[];
      emailType: SendableEmailType;
    }
  | { kind: "mark_resolved"; rows: FailedPayment[] }
  | { kind: "exclude"; rows: FailedPayment[] };

export interface BulkActionToolbarProps {
  selectedRows: FailedPayment[];
  isPending: boolean;
  pendingLabel?: string;
  onSendRecommended: (selections: BatchSelection[], skipped: FailedPayment[]) => void;
  onSendSpecific: (selections: BatchSelection[], emailType: SendableEmailType) => void;
  onMarkResolved: (rows: FailedPayment[]) => void;
  onExclude: (rows: FailedPayment[]) => void;
  onDeselectAll: () => void;
}

function subscriberDisplay(row: FailedPayment): string {
  return row.subscriber_email || row.subscriber_stripe_customer_id;
}

function isEligibleForSend(row: FailedPayment): boolean {
  return row.subscriber_status === "active" && !row.excluded_from_automation;
}

function deriveRecommended(rows: FailedPayment[]): {
  selections: BatchSelection[];
  eligibleRows: FailedPayment[];
  skippedNoRecommendation: FailedPayment[];
  skippedNotEligible: FailedPayment[];
} {
  const selections: BatchSelection[] = [];
  const eligibleRows: FailedPayment[] = [];
  const skippedNoRecommendation: FailedPayment[] = [];
  const skippedNotEligible: FailedPayment[] = [];
  for (const row of rows) {
    if (!isEligibleForSend(row)) {
      skippedNotEligible.push(row);
      continue;
    }
    if (row.recommended_email_type !== null) {
      selections.push({
        subscriber_id: row.subscriber_id,
        failure_id: row.id,
        email_type: row.recommended_email_type,
      });
      eligibleRows.push(row);
    } else {
      skippedNoRecommendation.push(row);
    }
  }
  return { selections, eligibleRows, skippedNoRecommendation, skippedNotEligible };
}

function deriveSpecific(
  rows: FailedPayment[],
  emailType: SendableEmailType,
): { selections: BatchSelection[]; eligibleRows: FailedPayment[] } {
  const eligibleRows = rows.filter(isEligibleForSend);
  const selections = eligibleRows.map((r) => ({
    subscriber_id: r.subscriber_id,
    failure_id: r.id,
    email_type: emailType,
  }));
  return { selections, eligibleRows };
}

function rollupLine(selections: BatchSelection[]): string {
  const counts: Record<string, number> = {};
  for (const s of selections) {
    counts[s.email_type] = (counts[s.email_type] ?? 0) + 1;
  }
  return Object.entries(counts)
    .map(([type, n]) => `${EMAIL_TYPE_LABELS[type as SendableEmailType]} ×${n}`)
    .join(" · ");
}

function ConfirmDialog({
  payload,
  isPending,
  pendingLabel,
  onCancel,
  onConfirm,
}: {
  payload: DialogPayload;
  isPending: boolean;
  pendingLabel?: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  let title = "";
  let primaryLabel = "";
  let body: React.ReactNode = null;

  if (payload.kind === "send_recommended") {
    const n = payload.selections.length;
    const noRec = payload.skippedNoRecommendation.length;
    const notEligible = payload.skippedNotEligible.length;
    title = `Send ${n} dunning email${n !== 1 ? "s" : ""}?`;
    primaryLabel = "Send all";
    body = (
      <div className="space-y-3">
        <ul className="max-h-48 overflow-y-auto space-y-1 text-sm">
          {payload.eligibleRows.map((row) => (
            <li key={row.id}>
              <span className="font-medium">{subscriberDisplay(row)}</span>
              <span className="text-muted-foreground">
                {" "}
                · {EMAIL_TYPE_LABELS[row.recommended_email_type as SendableEmailType]}
              </span>
            </li>
          ))}
        </ul>
        {n > 0 && (
          <p className="text-sm text-muted-foreground">{rollupLine(payload.selections)}</p>
        )}
        {noRec > 0 && (
          <p className="text-sm text-muted-foreground">
            Skipped (no recommendation): {noRec}
          </p>
        )}
        {notEligible > 0 && (
          <p className="text-sm text-muted-foreground">
            Skipped (not eligible): {notEligible}
          </p>
        )}
      </div>
    );
  } else if (payload.kind === "send_specific") {
    const n = payload.selections.length;
    const label = EMAIL_TYPE_LABELS[payload.emailType];
    title = `Send ${n} ${label} email${n !== 1 ? "s" : ""}?`;
    primaryLabel = "Send all";
    body = (
      <ul className="max-h-48 overflow-y-auto space-y-1 text-sm">
        {payload.eligibleRows.map((row) => (
          <li key={row.id}>{subscriberDisplay(row)}</li>
        ))}
      </ul>
    );
  } else if (payload.kind === "mark_resolved") {
    const n = payload.rows.length;
    title = `Mark ${n} as resolved?`;
    primaryLabel = "Mark resolved";
    body = (
      <ul className="max-h-48 overflow-y-auto space-y-1 text-sm">
        {payload.rows.map((r) => (
          <li key={r.id}>
            <span className="font-medium">{subscriberDisplay(r)}</span>
            <span className="text-muted-foreground"> · {r.subscriber_status}</span>
          </li>
        ))}
      </ul>
    );
  } else {
    const n = payload.rows.length;
    title = `Exclude ${n} from future recommendations?`;
    primaryLabel = "Exclude all";
    body = (
      <ul className="max-h-48 overflow-y-auto space-y-1 text-sm">
        {payload.rows.map((r) => (
          <li key={r.id}>{subscriberDisplay(r)}</li>
        ))}
      </ul>
    );
  }

  const primaryDisabled =
    isPending ||
    (payload.kind === "send_recommended" && payload.selections.length === 0) ||
    (payload.kind === "send_specific" && payload.selections.length === 0);

  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>Review the selection below.</DialogDescription>
        </DialogHeader>
        {body}
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={primaryDisabled}>
            {isPending ? pendingLabel ?? "Working…" : primaryLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function BulkActionToolbar({
  selectedRows,
  isPending,
  pendingLabel,
  onSendRecommended,
  onSendSpecific,
  onMarkResolved,
  onExclude,
  onDeselectAll,
}: BulkActionToolbarProps) {
  const [payload, setPayload] = useState<DialogPayload | null>(null);
  const n = selectedRows.length;

  if (n === 0) return null;

  const recommended = deriveRecommended(selectedRows);
  const recommendedDisabled = isPending || recommended.selections.length === 0;

  const specificEligibility: Record<SendableEmailType, number> =
    SPECIFIC_OPTIONS.reduce(
      (acc, opt) => {
        acc[opt.type] = deriveSpecific(selectedRows, opt.type).selections.length;
        return acc;
      },
      {} as Record<SendableEmailType, number>,
    );
  const anySpecificEligible = SPECIFIC_OPTIONS.some(
    (opt) => specificEligibility[opt.type] > 0,
  );
  const specificDropdownDisabled = isPending || !anySpecificEligible;

  const handleConfirm = () => {
    if (!payload) return;
    if (payload.kind === "send_recommended") {
      onSendRecommended(payload.selections, [
        ...payload.skippedNoRecommendation,
        ...payload.skippedNotEligible,
      ]);
    } else if (payload.kind === "send_specific") {
      onSendSpecific(payload.selections, payload.emailType);
    } else if (payload.kind === "mark_resolved") {
      onMarkResolved(payload.rows);
    } else if (payload.kind === "exclude") {
      onExclude(payload.rows);
    }
    setPayload(null);
  };

  return (
    <>
      <div
        role="toolbar"
        aria-label="Bulk actions"
        className="fixed bottom-0 left-0 right-0 z-50 border-t border-[var(--sn-border)] bg-[var(--bg-surface)] px-4 py-3 shadow-lg"
      >
        <div className="mx-auto flex max-w-[1280px] items-center justify-between gap-4">
          <span aria-live="polite" aria-atomic="true" className="text-sm text-[var(--text-secondary)]">
            {n} row{n !== 1 ? "s" : ""} selected
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onDeselectAll}
              className="text-sm text-[var(--text-secondary)] underline hover:text-[var(--text-primary)]"
            >
              Deselect all
            </button>
            <Button
              variant="ghost"
              size="sm"
              disabled={isPending}
              aria-label={`Exclude ${n}`}
              onClick={() => setPayload({ kind: "exclude", rows: selectedRows })}
            >
              Exclude ({n})
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={isPending}
              aria-label={`Mark resolved ${n}`}
              onClick={() => setPayload({ kind: "mark_resolved", rows: selectedRows })}
            >
              Mark resolved ({n})
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={specificDropdownDisabled}
                    aria-label="Send specific email"
                  />
                }
              >
                Send specific…
                <ChevronDownIcon className="ml-1 h-3 w-3" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {SPECIFIC_OPTIONS.map((opt) => {
                  const eligibleCount = specificEligibility[opt.type];
                  return (
                    <DropdownMenuItem
                      key={opt.type}
                      disabled={eligibleCount === 0}
                      onClick={() => {
                        const { selections, eligibleRows } = deriveSpecific(
                          selectedRows,
                          opt.type,
                        );
                        setPayload({
                          kind: "send_specific",
                          selections,
                          eligibleRows,
                          emailType: opt.type,
                        });
                      }}
                    >
                      {opt.label}
                    </DropdownMenuItem>
                  );
                })}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              size="sm"
              disabled={recommendedDisabled}
              aria-label={`Send recommended ${n}`}
              onClick={() =>
                setPayload({
                  kind: "send_recommended",
                  selections: recommended.selections,
                  eligibleRows: recommended.eligibleRows,
                  skippedNoRecommendation: recommended.skippedNoRecommendation,
                  skippedNotEligible: recommended.skippedNotEligible,
                })
              }
            >
              Send recommended ({n})
            </Button>
          </div>
        </div>
      </div>
      {payload !== null && (
        <ConfirmDialog
          payload={payload}
          isPending={isPending}
          pendingLabel={pendingLabel}
          onCancel={() => setPayload(null)}
          onConfirm={handleConfirm}
        />
      )}
    </>
  );
}
