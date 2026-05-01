"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowDownIcon, ArrowUpIcon, ChevronDownIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/subscriber/StatusBadge";
import { BulkActionToolbar } from "@/components/dashboard/BulkActionToolbar";
import { useAccount } from "@/hooks/useAccount";
import {
  useBatchSendEmail,
  type BatchSelection,
  type BatchSendResult,
} from "@/hooks/useBatchSendEmail";
import { useBulkFanout } from "@/hooks/useBulkFanout";
import { useDpaGate } from "@/hooks/useDpaGate";
import { useExcludeSubscriber } from "@/hooks/useExcludeSubscriber";
import { useFailedPayments } from "@/hooks/useFailedPayments";
import { useMarkResolved } from "@/hooks/useMarkResolved";
import {
  useSendEmail,
  SendEmailError,
  type SendableEmailType,
} from "@/hooks/useSendEmail";
import { cn } from "@/lib/utils";
import {
  formatCurrency,
  formatDate,
  formatRelativeTime,
} from "@/lib/formatters";
import type {
  FailedPayment,
  RecommendedEmailType,
  SortDirection,
  SortKey,
} from "@/types/failed_payment";

const TIER_TOOLTIP = "Upgrade to Mid or Pro to enable email actions";

const SPECIFIC_EMAIL_OPTIONS: Array<{ type: SendableEmailType; label: string }> = [
  { type: "update_payment", label: "Update payment" },
  { type: "retry_reminder", label: "Retry reminder" },
  { type: "final_notice", label: "Final notice" },
];

function labelFor(t: SendableEmailType): string {
  return SPECIFIC_EMAIL_OPTIONS.find((o) => o.type === t)?.label ?? t;
}

const RECOMMENDED_EMAIL_LABELS: Record<
  Exclude<RecommendedEmailType, null>,
  string
> = {
  update_payment: "Update payment",
  retry_reminder: "Retry reminder",
  final_notice: "Final notice",
};

function RecommendedEmailChip({ type }: { type: RecommendedEmailType }) {
  if (!type) {
    return <span className="text-[var(--text-secondary)]">—</span>;
  }
  return (
    <span className="inline-flex items-center rounded-full bg-[var(--accent-active)]/15 px-2 py-0.5 text-[11px] font-medium text-[var(--accent-active)]">
      {RECOMMENDED_EMAIL_LABELS[type]}
    </span>
  );
}

function useSortFromUrl(): {
  sort: SortKey;
  dir: SortDirection;
  setSort: (key: SortKey) => void;
} {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const sort: SortKey = params.get("sort") === "amount" ? "amount" : "date";
  const dir: SortDirection = params.get("dir") === "asc" ? "asc" : "desc";

  const setSort = (key: SortKey) => {
    const next = new URLSearchParams(params.toString());
    if (key === sort) {
      next.set("dir", dir === "desc" ? "asc" : "desc");
    } else {
      next.set("sort", key);
      next.set("dir", "desc");
    }
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  };

  return { sort, dir, setSort };
}

function SortableHeader({
  label,
  active,
  direction,
  align,
  onClick,
}: {
  label: string;
  active: boolean;
  direction: SortDirection;
  align?: "left" | "right";
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 text-sm font-medium hover:underline",
        align === "right" && "justify-end"
      )}
    >
      {label}
      {active &&
        (direction === "desc" ? (
          <ArrowDownIcon className="h-3 w-3" />
        ) : (
          <ArrowUpIcon className="h-3 w-3" />
        ))}
    </button>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          data-testid="failed-payments-skeleton-row"
          className="grid grid-cols-8 gap-3 rounded-md border border-[var(--sn-border)] bg-[var(--bg-surface)] p-3"
        >
          {Array.from({ length: 8 }).map((__, j) => (
            <div
              key={j}
              className="h-4 animate-pulse rounded bg-[var(--sn-border)]"
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-[var(--sn-border)] bg-[var(--bg-surface)] p-12 text-center">
      <h3 className="text-lg font-semibold text-[var(--text-primary)]">
        No failed payments this month.
      </h3>
      <p className="mt-2 text-sm text-[var(--text-secondary)]">
        Your subscribers are paying — keep shipping.
      </p>
    </div>
  );
}

function ActionButtons({
  row,
  gateDisabled,
  gateTooltip,
}: {
  row: FailedPayment;
  gateDisabled: boolean;
  gateTooltip: string | undefined;
}) {
  const sendEmail = useSendEmail();
  const markResolved = useMarkResolved();
  const exclude = useExcludeSubscriber();

  const sendingEmailType = sendEmail.isPending
    ? sendEmail.variables?.emailType ?? null
    : null;
  const isPending = sendEmail.isPending || markResolved.isPending || exclude.isPending;
  const sendDisabled = gateDisabled || isPending;
  const recommendedDisabled = sendDisabled || row.recommended_email_type === null;
  const recommendedTitle =
    row.recommended_email_type === null
      ? "No recommendation available yet"
      : gateTooltip;

  const handleSend = (emailType: SendableEmailType) => {
    sendEmail.mutate(
      { subscriberId: row.subscriber_id, failureId: row.id, emailType },
      {
        onSuccess: () => {
          toast.success(`Queued ${labelFor(emailType)} email.`);
        },
        onError: (err) => {
          if (err.code === "RATE_LIMITED") {
            const seconds = err.retryAfterSeconds ?? 60;
            toast.error(`Rate limit reached. Try again in ${seconds}s.`, { duration: 6000 });
          } else if (err.code === "OPT_OUT") {
            toast.error("Subscriber has opted out of notifications.", { duration: 6000 });
          } else if (err.code === "EXCLUDED") {
            toast.error("Subscriber is excluded from automation.", { duration: 6000 });
          } else if (err.code === "DPA_REQUIRED") {
            toast.error("Sign the DPA to enable email sends.", { duration: Infinity });
          } else {
            toast.error(err.message || "Failed to queue email.", { duration: 6000 });
          }
        },
      },
    );
  };

  const handleMarkResolved = () => {
    markResolved.mutate(row.subscriber_id, {
      onSuccess: () => toast.success("Marked as resolved."),
      onError: () => toast.error("Failed to mark resolved.", { duration: 6000 }),
    });
  };

  const handleExclude = () => {
    exclude.mutate(row.subscriber_id, {
      onSuccess: () => toast.success("Excluded from future recommendations."),
      onError: () => toast.error("Failed to exclude subscriber.", { duration: 6000 }),
    });
  };

  return (
    <div className="flex justify-end gap-1">
      <Button
        size="sm"
        variant="default"
        disabled={recommendedDisabled}
        title={recommendedTitle}
        onClick={() =>
          row.recommended_email_type !== null && handleSend(row.recommended_email_type)
        }
        aria-label="Send recommended"
      >
        {sendingEmailType !== null && sendingEmailType === row.recommended_email_type
          ? "Sending…"
          : "Send recommended"}
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            size="sm"
            variant="ghost"
            disabled={sendDisabled}
            title={gateTooltip}
            aria-label="Send specific email"
          >
            <ChevronDownIcon className="h-3 w-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {SPECIFIC_EMAIL_OPTIONS.map((opt) => (
            <DropdownMenuItem
              key={opt.type}
              disabled={sendDisabled}
              onSelect={() => handleSend(opt.type)}
            >
              {opt.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <Button
        size="sm"
        variant="ghost"
        disabled={sendDisabled}
        title={gateTooltip}
        aria-label="Mark resolved"
        onClick={handleMarkResolved}
      >
        Mark resolved
      </Button>
      <Button
        size="sm"
        variant="ghost"
        disabled={sendDisabled}
        title={gateTooltip}
        aria-label="Exclude"
        onClick={handleExclude}
      >
        Exclude
      </Button>
    </div>
  );
}

function PaymentRow({
  row,
  gateDisabled,
  gateTooltip,
  isSelected,
  isFree,
  onToggleSelected,
}: {
  row: FailedPayment;
  gateDisabled: boolean;
  gateTooltip: string | undefined;
  isSelected: boolean;
  isFree: boolean;
  onToggleSelected: (rowId: number, checked: boolean) => void;
}) {
  const isFraud = row.subscriber_status === "fraud_flagged";
  const subscriberLabel = row.subscriber_email || row.subscriber_stripe_customer_id;
  return (
    <TableRow
      data-testid={`failed-payment-row-${row.id}`}
      data-fraud={isFraud ? "true" : "false"}
      className={cn(isFraud && "border-amber-500 border-2")}
    >
      <TableCell className="w-8">
        <Checkbox
          checked={isSelected}
          disabled={isFree}
          aria-label={`Select row for ${subscriberLabel}`}
          title={isFree ? TIER_TOOLTIP : undefined}
          onCheckedChange={(checked) => onToggleSelected(row.id, Boolean(checked))}
        />
      </TableCell>
      <TableCell>
        <div className="flex flex-col">
          <span className="font-medium text-[var(--text-primary)]">
            {subscriberLabel}
          </span>
          {row.subscriber_email && (
            <span className="text-xs text-[var(--text-secondary)]">
              {row.subscriber_stripe_customer_id}
            </span>
          )}
        </div>
      </TableCell>
      <TableCell>{row.decline_reason}</TableCell>
      <TableCell className="text-right">
        {formatCurrency(row.amount_cents, "EUR")}
      </TableCell>
      <TableCell>{formatDate(row.failure_created_at)}</TableCell>
      <TableCell>
        <RecommendedEmailChip type={row.recommended_email_type} />
      </TableCell>
      <TableCell>
        <StatusBadge status={row.subscriber_status} />
      </TableCell>
      <TableCell>
        {row.last_email_sent_at ? (
          formatRelativeTime(row.last_email_sent_at)
        ) : (
          <span className="text-[var(--text-secondary)]">—</span>
        )}
      </TableCell>
      <TableCell>
        <ActionButtons row={row} gateDisabled={gateDisabled} gateTooltip={gateTooltip} />
      </TableCell>
    </TableRow>
  );
}

export function FailedPaymentsList() {
  const { sort, dir, setSort } = useSortFromUrl();
  const { data, isLoading, isError } = useFailedPayments(sort, dir);
  const { sendDisabled, tooltip: dpaTooltip } = useDpaGate();
  const { data: account } = useAccount();
  const isFree = account?.tier === "free";

  let gateTooltip: string | undefined = undefined;
  if (isFree) {
    gateTooltip = TIER_TOOLTIP;
  } else if (sendDisabled && dpaTooltip) {
    gateTooltip = dpaTooltip;
  }
  const gateDisabled = isFree || sendDisabled;

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const batchSendEmail = useBatchSendEmail();
  const markResolvedFanout = useBulkFanout("mark-resolved");
  const excludeFanout = useBulkFanout("exclude");

  // Prune stale ids when `data` identity changes (sort/refetch returning a
  // different row set). Without this, selectedIds accumulates ghost ids and
  // the header indeterminate state can drift.
  useEffect(() => {
    if (!data) return;
    setSelectedIds((prev) => {
      const dataIds = new Set(data.map((r) => r.id));
      let changed = false;
      const next = new Set<number>();
      for (const id of prev) {
        if (dataIds.has(id)) next.add(id);
        else changed = true;
      }
      return changed ? next : prev;
    });
  }, [data]);

  const effectiveSelectedIds = isFree ? new Set<number>() : selectedIds;
  const selectedRows = (data ?? []).filter((r) => effectiveSelectedIds.has(r.id));

  const isAnyBulkPending =
    batchSendEmail.isPending || markResolvedFanout.isPending || excludeFanout.isPending;

  const toggleId = (rowId: number, checked: boolean) => {
    if (isFree) return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(rowId);
      else next.delete(rowId);
      return next;
    });
  };

  const handleSelectAll = (checked: boolean) => {
    if (isFree || !data) return;
    setSelectedIds(checked ? new Set(data.map((r) => r.id)) : new Set());
  };

  const handleBatchResult = (res: BatchSendResult) => {
    if (res.failed === 0) {
      toast.success(`Queued ${res.queued} dunning email${res.queued !== 1 ? "s" : ""}.`);
    } else if (res.queued > 0) {
      toast.warning(
        `Queued ${res.queued} of ${res.selections_total}. ${res.failed} failed.`,
        { duration: 8000 },
      );
    } else {
      toast.error("Could not queue any emails.", { duration: 6000 });
    }
    setSelectedIds(new Set());
  };

  const handleBatchError = (err: SendEmailError) => {
    if (err.code === "RATE_LIMITED") {
      const seconds = err.retryAfterSeconds ?? 60;
      toast.error(`Rate limit reached on bulk send. Try again in ${seconds}s.`, {
        duration: 6000,
      });
    } else if (err.code === "OPT_OUT") {
      toast.error("Subscriber has opted out of notifications.", { duration: 6000 });
    } else if (err.code === "EXCLUDED") {
      toast.error("Subscriber is excluded from automation.", { duration: 6000 });
    } else if (err.code === "DPA_REQUIRED") {
      toast.error("Sign the DPA to enable email sends.", { duration: Infinity });
    } else {
      toast.error(err.message || "Failed to queue emails.", { duration: 6000 });
    }
  };

  const handleFanoutResult = (verb: "Marked" | "Excluded") =>
    (res: { succeeded: number; failed: number; total: number }) => {
      if (res.failed === 0) {
        toast.success(`${verb} ${res.succeeded}.`);
      } else if (res.succeeded > 0) {
        toast.warning(
          `${verb} ${res.succeeded} of ${res.total} — ${res.failed} failed.`,
          { duration: 8000 },
        );
      } else {
        toast.error(`Failed to ${verb.toLowerCase()} ${res.total}.`, {
          duration: 6000,
        });
      }
      setSelectedIds(new Set());
    };

  const onSendBulk = (selections: BatchSelection[]) => {
    batchSendEmail.mutate(selections, {
      onSuccess: handleBatchResult,
      onError: handleBatchError,
    });
  };

  const onMarkResolvedBulk = (rows: FailedPayment[]) => {
    const uniqueSubscriberIds = Array.from(
      new Set(rows.map((r) => r.subscriber_id)),
    );
    markResolvedFanout
      .run(uniqueSubscriberIds)
      .then(handleFanoutResult("Marked"));
  };

  const onExcludeBulk = (rows: FailedPayment[]) => {
    const uniqueSubscriberIds = Array.from(
      new Set(rows.map((r) => r.subscriber_id)),
    );
    excludeFanout
      .run(uniqueSubscriberIds)
      .then(handleFanoutResult("Excluded"));
  };

  const allRendered = data?.length ?? 0;
  const headerChecked =
    allRendered > 0 && selectedRows.length === allRendered;
  const headerIndeterminate =
    selectedRows.length > 0 && selectedRows.length < allRendered;

  let pendingLabel: string | undefined;
  if (batchSendEmail.isPending) pendingLabel = "Sending…";
  else if (markResolvedFanout.isPending) pendingLabel = "Marking resolved…";
  else if (excludeFanout.isPending) pendingLabel = "Excluding…";

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
        Failed payments this month
      </h2>

      {isFree && (
        <div className="mb-4 rounded-md border border-[var(--sn-border)] bg-[var(--bg-surface)] p-3 text-sm">
          <span className="text-[var(--text-secondary)]">
            View-only on Free tier.{" "}
          </span>
          <Link
            href="/settings#subscription"
            className="font-medium text-[var(--accent-active)] hover:underline"
          >
            Upgrade to send dunning emails →
          </Link>
        </div>
      )}

      {isError ? (
        <div
          role="alert"
          className="rounded-md border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-700 dark:text-red-300"
        >
          Failed to load failed payments. Please retry in a moment.
        </div>
      ) : isLoading || !data ? (
        <ListSkeleton />
      ) : data.length === 0 ? (
        <EmptyState />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-8">
                <Checkbox
                  checked={headerChecked}
                  indeterminate={headerIndeterminate}
                  disabled={isFree}
                  aria-label="Select all visible rows"
                  title={isFree ? TIER_TOOLTIP : undefined}
                  onCheckedChange={(checked) => handleSelectAll(Boolean(checked))}
                />
              </TableHead>
              <TableHead>Subscriber</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead className="text-right">
                <SortableHeader
                  label="Amount"
                  active={sort === "amount"}
                  direction={dir}
                  align="right"
                  onClick={() => setSort("amount")}
                />
              </TableHead>
              <TableHead>
                <SortableHeader
                  label="Date"
                  active={sort === "date"}
                  direction={dir}
                  onClick={() => setSort("date")}
                />
              </TableHead>
              <TableHead>Recommended email</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Last email</TableHead>
              <TableHead className="sr-only">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <PaymentRow
                key={row.id}
                row={row}
                gateDisabled={gateDisabled}
                gateTooltip={gateTooltip}
                isSelected={effectiveSelectedIds.has(row.id)}
                isFree={!!isFree}
                onToggleSelected={toggleId}
              />
            ))}
          </TableBody>
        </Table>
      )}

      <BulkActionToolbar
        selectedRows={selectedRows}
        isPending={isAnyBulkPending}
        pendingLabel={pendingLabel}
        onSendRecommended={(selections) => onSendBulk(selections)}
        onSendSpecific={(selections) => onSendBulk(selections)}
        onMarkResolved={onMarkResolvedBulk}
        onExclude={onExcludeBulk}
        onDeselectAll={() => setSelectedIds(new Set())}
      />
    </section>
  );
}
