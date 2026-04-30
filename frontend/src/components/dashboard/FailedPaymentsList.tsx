"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowDownIcon, ArrowUpIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
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
import { useFailedPayments } from "@/hooks/useFailedPayments";
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

const PLACEHOLDER_TOOLTIP = "Coming in next release";
const TIER_TOOLTIP = "Upgrade to Mid or Pro to enable email actions";

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
  disabled,
  tooltip,
}: {
  disabled: boolean;
  tooltip: string;
}) {
  return (
    <div className="flex justify-end gap-1">
      {(["Send", "Mark resolved", "Exclude"] as const).map((label) => (
        <Button
          key={label}
          variant="ghost"
          size="sm"
          disabled={disabled}
          title={tooltip}
          aria-label={label}
        >
          {label}
        </Button>
      ))}
    </div>
  );
}

function PaymentRow({
  row,
  actionsDisabled,
  actionsTooltip,
}: {
  row: FailedPayment;
  actionsDisabled: boolean;
  actionsTooltip: string;
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
        <ActionButtons disabled={actionsDisabled} tooltip={actionsTooltip} />
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

  // Tooltip precedence: tier > DPA > placeholder. Stories 3.3/3.4 lift the
  // placeholder gate; for 3.2 every action button is a disabled placeholder.
  let actionsTooltip = PLACEHOLDER_TOOLTIP;
  if (isFree) {
    actionsTooltip = TIER_TOOLTIP;
  } else if (sendDisabled && dpaTooltip) {
    actionsTooltip = dpaTooltip;
  }
  const actionsDisabled = true;

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
                actionsDisabled={actionsDisabled}
                actionsTooltip={actionsTooltip}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
