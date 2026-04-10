import { create } from "zustand";
import type { User } from "@/types";

interface AuthState {
  // Note: actual tokens live in httpOnly cookies (XSS-safe).
  // authStore tracks identity only — NOT raw token strings.
  user: User | null;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  setUser: (user) => set({ user, isAuthenticated: user !== null }),
  clearAuth: () => set({ user: null, isAuthenticated: false }),
}));
