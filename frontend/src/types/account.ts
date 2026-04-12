/**
 * TypeScript interfaces for Account and User API responses.
 * All fields use snake_case — mirrors Django API contract exactly.
 * No transformation layer.
 */

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
}

export interface Account {
  id: number;
  owner_email?: string; // backward compat
  owner: User;
  company_name: string;
  tier: "free" | "mid" | "pro";
  trial_ends_at: string | null; // ISO 8601 or null
  is_on_trial: boolean;
  stripe_connected: boolean;
  profile_complete: boolean;
  created_at: string; // ISO 8601
}

export interface StripeConnection {
  id: number;
  account_id: number;
  stripe_user_id: string;
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}
