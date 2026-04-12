import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Mock next/navigation
const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn(), back: vi.fn(), forward: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

// Mock api — use vi.hoisted to avoid hoisting issues
const { mockPost } = vi.hoisted(() => ({ mockPost: vi.fn() }));
vi.mock("@/lib/api", () => ({
  default: { post: mockPost },
}));

import CompleteProfilePage from "@/app/(auth)/register/complete/page";

describe("CompleteProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.cookie = "safenet_profile_complete=;path=/;max-age=0";
  });

  it("renders all form fields", () => {
    render(<CompleteProfilePage />);
    expect(screen.getByLabelText("First name")).toBeDefined();
    expect(screen.getByLabelText("Last name")).toBeDefined();
    expect(screen.getByLabelText("Company or SaaS name")).toBeDefined();
    expect(screen.getByLabelText("Password")).toBeDefined();
    expect(screen.getByLabelText("Confirm password")).toBeDefined();
    expect(screen.getByRole("button", { name: /complete setup/i })).toBeDefined();
  });

  it("calls correct API endpoint on submit", async () => {
    mockPost.mockResolvedValueOnce({ data: { data: { profile_complete: true } } });
    render(<CompleteProfilePage />);

    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Marc" } });
    fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Dupont" } });
    fireEvent.change(screen.getByLabelText("Company or SaaS name"), { target: { value: "TestCo" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "SecurePass!2026" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "SecurePass!2026" } });

    fireEvent.click(screen.getByRole("button", { name: /complete setup/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith("/account/complete-profile/", {
        first_name: "Marc",
        last_name: "Dupont",
        company_name: "TestCo",
        password: "SecurePass!2026",
        password_confirm: "SecurePass!2026",
      });
    });
  });

  it("displays validation errors inline", async () => {
    mockPost.mockRejectedValueOnce({
      response: {
        data: {
          error: {
            code: "VALIDATION_ERROR",
            message: "Passwords do not match.",
            field: "password_confirm",
          },
        },
      },
    });

    render(<CompleteProfilePage />);

    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Marc" } });
    fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Dupont" } });
    fireEvent.change(screen.getByLabelText("Company or SaaS name"), { target: { value: "TestCo" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "pass1" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "pass2" } });

    fireEvent.click(screen.getByRole("button", { name: /complete setup/i }));

    await waitFor(() => {
      expect(screen.getByText("Passwords do not match.")).toBeDefined();
    });
  });

  it("redirects to dashboard on success", async () => {
    mockPost.mockResolvedValueOnce({ data: { data: { profile_complete: true } } });
    render(<CompleteProfilePage />);

    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Marc" } });
    fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Dupont" } });
    fireEvent.change(screen.getByLabelText("Company or SaaS name"), { target: { value: "TestCo" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "SecurePass!2026" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "SecurePass!2026" } });

    fireEvent.click(screen.getByRole("button", { name: /complete setup/i }));

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/dashboard");
    });
  });
});
