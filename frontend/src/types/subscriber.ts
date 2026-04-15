export interface SubscriberCard {
  id: number;
  stripe_customer_id: string;
  email: string;
  status: "active" | "recovered" | "passive_churn" | "fraud_flagged";
  decline_code: string | null;
  decline_reason: string | null;
  amount_cents: number | null;
  needs_attention: boolean;
  excluded_from_automation: boolean;
}
