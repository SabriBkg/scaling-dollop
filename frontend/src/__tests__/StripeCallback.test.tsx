import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";

// Mock next/navigation
const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn(), back: vi.fn(), forward: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams("code=ac_test&state=test_state"),
}));

// Mock auth
const { mockSetTokens } = vi.hoisted(() => ({ mockSetTokens: vi.fn() }));
vi.mock("@/lib/auth", () => ({
  setTokens: (...args: unknown[]) => mockSetTokens(...args),
}));

// Mock api
const { mockPost } = vi.hoisted(() => ({ mockPost: vi.fn() }));
vi.mock("@/lib/api", () => ({
  default: { post: mockPost },
}));

import StripeCallbackPage from "@/app/(auth)/register/callback/page";

describe("StripeCallbackPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.cookie = "safenet_profile_complete=;path=/;max-age=0";
  });

  it("redirects to /register/complete for new accounts", async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        data: {
          access: "test_access",
          refresh: "test_refresh",
          account_id: 1,
          is_new_account: true,
          profile_complete: false,
        },
      },
    });
    mockSetTokens.mockResolvedValueOnce(true);

    render(<StripeCallbackPage />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/register/complete");
    });
  });

  it("redirects to /dashboard for returning users with complete profile", async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        data: {
          access: "test_access",
          refresh: "test_refresh",
          account_id: 1,
          is_new_account: false,
          profile_complete: true,
        },
      },
    });
    mockSetTokens.mockResolvedValueOnce(true);

    render(<StripeCallbackPage />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/dashboard");
    });
  });
});
