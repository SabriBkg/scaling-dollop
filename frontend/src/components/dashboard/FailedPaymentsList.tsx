"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowDownIcon, ArrowUpIcon, ChevronDownIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
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
import { useAccount } from "@/hooks/useAccount";
import { useDpaGate } from "@/hooks/useDpaGate";
import { useExcludeSubscriber } from "@/hooks/useExcludeSubscriber";
import { useFailedPayments } from "@/hooks/useFailedPayments";
import { useMarkResolved } from "@/hooks/useMarkResolved";
import { useSendEmail, type SendableEmailType } from "@/hooks/useSendEmail";
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
}: {
  row: FailedPayment;
  gateDisabled: boolean;
  gateTooltip: string | undefined;
}) {
  const isFraud = row.subscriber_status === "fraud_flagged";
  const subscriberLabel = row.subscriber_email || row.subscriber_stripe_customer_id;
  return (
    <TableRow
      data-testid={`failed-payment-row-${row.id}`}
      data-fraud={isFraud ? "true" : "false"}
      className={cn(isFraud && "border-amber-500 border-2")}
    >
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

  // Tooltip precedence: tier > DPA. Story 3.3 v1 wires real mutations;
  // each per-row mutation hook surfaces its own pending state and toast.
  let gateTooltip: string | undefined = undefined;
  if (isFree) {
    gateTooltip = TIER_TOOLTIP;
  } else if (sendDisabled && dpaTooltip) {
    gateTooltip = dpaTooltip;
  }
  const gateDisabled = isFree || sendDisabled;

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
              />
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
