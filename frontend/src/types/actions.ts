export interface PendingAction {
  id: number;
  subscriber_name: string;
  decline_reason: string;
  recommended_action: string;
  amount_cents: number;
  created_at: string;
  failure_id: number;
  subscriber_id: number;
}

export interface BatchResult {
  approved: number;
  failed: number;
  failures: Array<{ id: number; error: string }>;
}
