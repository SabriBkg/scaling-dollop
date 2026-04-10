export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export const ROUTES = {
  LOGIN: "/login",
  REGISTER: "/register",
  STRIPE_CALLBACK: "/register/callback",
  DASHBOARD: "/dashboard",
  SETTINGS: "/settings",
  REVIEW_QUEUE: "/review-queue",
} as const;
