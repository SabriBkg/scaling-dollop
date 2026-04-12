export interface DeclineBreakdownEntry {
  decline_code: string;
  human_label: string;
  subscriber_count: number;
  total_amount_cents: number;
  recovery_action: "retry_notify" | "notify_only" | "fraud_flag" | "no_action";
}

export interface DashboardSummary {
  total_failures: number;
  total_subscribers: number;
  estimated_recoverable_cents: number;
  recovered_this_month_cents: number;
  recovered_count: number;
  recovery_rate: number;
  net_benefit_cents: number;
  decline_breakdown: DeclineBreakdownEntry[];
}
