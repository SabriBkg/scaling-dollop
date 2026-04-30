import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { FailedPaymentsList } from "@/components/dashboard/FailedPaymentsList";
import { formatCurrency } from "@/lib/formatters";
import type { FailedPayment } from "@/types/failed_payment";

const mockUseFailedPayments = vi.fn();
const mockUseDpaGate = vi.fn();
const mockUseAccount = vi.fn();
const mockReplace = vi.fn();
const mockSearchParams = new URLSearchParams();

vi.mock("@/hooks/useFailedPayments", () => ({
  useFailedPayments: (...args: unknown[]) => mockUseFailedPayments(...args),
}));

vi.mock("@/hooks/useDpaGate", () => ({
  useDpaGate: () => mockUseDpaGate(),
}));

vi.mock("@/hooks/useAccount", () => ({
  useAccount: () => mockUseAccount(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  usePathname: () => "/dashboard",
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

function makeRow(overrides: Partial<FailedPayment> = {}): FailedPayment {
  return {
    id: 1,
    subscriber_id: 1,
    subscriber_email: "alice@example.com",
    subscriber_stripe_customer_id: "cus_alice",
    subscriber_status: "active",
    decline_code: "insufficient_funds",
    decline_reason: "Insufficient funds",
    amount_cents: 5000,
    failure_created_at: "2026-04-15T10:00:00Z",
    recommended_email_type: null,
    last_email_sent_at: null,
    payment_method_country: "FR",
    excluded_from_automation: false,
    ...overrides,
  };
}

function setMidTierWithDpa() {
  mockUseAccount.mockReturnValue({
    data: {
      id: 1,
      tier: "mid",
      dpa_accepted: true,
      dpa_version: "v1.0-2026-04-29",
    },
    isLoading: false,
  });
  mockUseDpaGate.mockReturnValue({
    dpaAccepted: true,
    loading: false,
    sendDisabled: false,
    tooltip: undefined,
    activatePath: "/activate",
  });
}

describe("FailedPaymentsList", () => {
  beforeEach(() => {
    mockUseFailedPayments.mockReset();
    mockUseDpaGate.mockReset();
    mockUseAccount.mockReset();
    mockReplace.mockReset();
    // Default URL params clean
    mockSearchParams.forEach((_, k) => mockSearchParams.delete(k));
    setMidTierWithDpa();
  });

  it("renders empty state when data is empty", () => {
    mockUseFailedPayments.mockReturnValue({ data: [], isLoading: false });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    expect(
      screen.getByText("No failed payments this month.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Your subscribers are paying — keep shipping.")
    ).toBeInTheDocument();
  });

  it("renders skeleton while loading", () => {
    mockUseFailedPayments.mockReturnValue({ data: undefined, isLoading: true });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    expect(
      screen.getAllByTestId("failed-payments-skeleton-row")
    ).toHaveLength(5);
  });

  it("renders one row per failed payment", () => {
    mockUseFailedPayments.mockReturnValue({
      data: [
        makeRow({ id: 1 }),
        makeRow({ id: 2, subscriber_email: "bob@example.com" }),
        makeRow({ id: 3, subscriber_email: "carol@example.com" }),
      ],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    const tbody = document.querySelector("tbody")!;
    expect(within(tbody).getAllByRole("row")).toHaveLength(3);
  });

  it("formats amount as EUR", () => {
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ amount_cents: 5000 })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    expect(screen.getByText(formatCurrency(5000, "EUR"))).toBeInTheDocument();
  });

  it("applies amber border to fraud-flagged rows", () => {
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ id: 7, subscriber_status: "fraud_flagged" })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    const row = screen.getByTestId("failed-payment-row-7");
    expect(row.className).toContain("border-amber-500");
    expect(row.className).toContain("border-2");
  });

  it("recommended email chip shows em-dash for null type", () => {
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ recommended_email_type: null })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    // multiple — could exist; assert at least one
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("recommended email chip shows label for non-null type", () => {
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ recommended_email_type: "update_payment" })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    expect(screen.getByText("Update payment")).toBeInTheDocument();
  });

  it("last email shows em-dash when null", () => {
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ last_email_sent_at: null })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("clicking Amount header toggles sort direction", () => {
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow()],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByRole("button", { name: /Amount/i }));
    expect(mockReplace).toHaveBeenCalled();
    const url: string = mockReplace.mock.calls[0][0];
    expect(url).toContain("sort=amount");
    expect(url).toContain("dir=desc");
  });

  it("clicking Date header switches sort key + resets dir to desc", () => {
    mockSearchParams.set("sort", "amount");
    mockSearchParams.set("dir", "asc");
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow()],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByRole("button", { name: /Date/i }));
    expect(mockReplace).toHaveBeenCalled();
    const url: string = mockReplace.mock.calls[0][0];
    expect(url).toContain("sort=date");
    expect(url).toContain("dir=desc");
  });

  it("Free tier shows upgrade banner", () => {
    mockUseAccount.mockReturnValue({
      data: { id: 1, tier: "free", dpa_accepted: false },
      isLoading: false,
    });
    mockUseDpaGate.mockReturnValue({
      dpaAccepted: false,
      loading: false,
      sendDisabled: true,
      tooltip: "Sign the DPA to enable email sends",
      activatePath: "/activate",
    });
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow()],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    expect(screen.getByText("View-only on Free tier.")).toBeInTheDocument();
    const link = screen.getByText("Upgrade to send dunning emails →");
    expect(link.getAttribute("href")).toBe("/settings#subscription");
  });

  it("Free tier disables action buttons with tier tooltip", () => {
    mockUseAccount.mockReturnValue({
      data: { id: 1, tier: "free", dpa_accepted: false },
      isLoading: false,
    });
    mockUseDpaGate.mockReturnValue({
      dpaAccepted: false,
      loading: false,
      sendDisabled: true,
      tooltip: "Sign the DPA to enable email sends",
      activatePath: "/activate",
    });
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow()],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    const sendBtn = screen.getByRole("button", { name: "Send" });
    expect(sendBtn).toBeDisabled();
    expect(sendBtn.getAttribute("title")).toBe(
      "Upgrade to Mid or Pro to enable email actions"
    );
  });

  it("Mid tier without DPA disables action buttons with DPA tooltip", () => {
    mockUseAccount.mockReturnValue({
      data: { id: 1, tier: "mid", dpa_accepted: false },
      isLoading: false,
    });
    mockUseDpaGate.mockReturnValue({
      dpaAccepted: false,
      loading: false,
      sendDisabled: true,
      tooltip: "Sign the DPA to enable email sends",
      activatePath: "/activate",
    });
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow()],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    const sendBtn = screen.getByRole("button", { name: "Send" });
    expect(sendBtn).toBeDisabled();
    expect(sendBtn.getAttribute("title")).toBe(
      "Sign the DPA to enable email sends"
    );
  });

  it("Mid tier with DPA accepted shows placeholder tooltip", () => {
    setMidTierWithDpa();
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow()],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    const sendBtn = screen.getByRole("button", { name: "Send" });
    expect(sendBtn).toBeDisabled();
    expect(sendBtn.getAttribute("title")).toBe("Coming in next release");
  });
});
