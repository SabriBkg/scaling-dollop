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
  owner: User;
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
