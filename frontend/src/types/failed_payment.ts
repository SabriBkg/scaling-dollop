export type RecommendedEmailType =
  | "update_payment"
  | "retry_reminder"
  | "final_notice"
  | null;

export interface FailedPayment {
  id: number;
  subscriber_id: number;
  subscriber_email: string | null;
  subscriber_stripe_customer_id: string;
  subscriber_status: "active" | "recovered" | "passive_churn" | "fraud_flagged";
  decline_code: string;
  decline_reason: string;
  amount_cents: number;
  failure_created_at: string;
  recommended_email_type: RecommendedEmailType;
  last_email_sent_at: string | null;
  payment_method_country: string | null;
  excluded_from_automation: boolean;
}

export type SortKey = "date" | "amount";
export type SortDirection = "asc" | "desc";
