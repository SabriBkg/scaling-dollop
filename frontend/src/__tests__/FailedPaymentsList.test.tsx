import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { FailedPaymentsList } from "@/components/dashboard/FailedPaymentsList";
import { formatCurrency } from "@/lib/formatters";
import type { FailedPayment } from "@/types/failed_payment";

const {
  mockUseFailedPayments,
  mockUseDpaGate,
  mockUseAccount,
  mockReplace,
  mockSearchParams,
  mockSendEmailMutate,
  mockMarkResolvedMutate,
  mockExcludeMutate,
  mockToastError,
  mockToastSuccess,
  mockSendEmailHookRef,
} = vi.hoisted(() => {
  const refs = {
    mockUseFailedPayments: vi.fn(),
    mockUseDpaGate: vi.fn(),
    mockUseAccount: vi.fn(),
    mockReplace: vi.fn(),
    mockSearchParams: new URLSearchParams(),
    mockSendEmailMutate: vi.fn(),
    mockMarkResolvedMutate: vi.fn(),
    mockExcludeMutate: vi.fn(),
    mockToastError: vi.fn(),
    mockToastSuccess: vi.fn(),
    mockSendEmailHookRef: { current: { mutate: vi.fn(), isPending: false, variables: undefined as unknown } },
  };
  refs.mockSendEmailHookRef.current.mutate = refs.mockSendEmailMutate;
  return refs;
});

vi.mock("@/hooks/useFailedPayments", () => ({
  useFailedPayments: (...args: unknown[]) => mockUseFailedPayments(...args),
}));

vi.mock("@/hooks/useDpaGate", () => ({
  useDpaGate: () => mockUseDpaGate(),
}));

vi.mock("@/hooks/useAccount", () => ({
  useAccount: () => mockUseAccount(),
}));

vi.mock("@/hooks/useSendEmail", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/useSendEmail")>(
    "@/hooks/useSendEmail",
  );
  return {
    ...actual,
    useSendEmail: () => mockSendEmailHookRef.current,
  };
});

vi.mock("@/hooks/useMarkResolved", () => ({
  useMarkResolved: () => ({ mutate: mockMarkResolvedMutate, isPending: false }),
}));

vi.mock("@/hooks/useExcludeSubscriber", () => ({
  useExcludeSubscriber: () => ({ mutate: mockExcludeMutate, isPending: false }),
}));

vi.mock("sonner", () => ({
  toast: { error: mockToastError, success: mockToastSuccess, warning: vi.fn() },
}));

// Radix DropdownMenu is hard to drive via fireEvent in jsdom (it uses an
// internal pointer-event lifecycle to fire onSelect). Replace with a flat
// passthrough so menuitem clicks call onSelect directly.
vi.mock("@/components/ui/dropdown-menu", async () => {
  const React = await import("react");
  const Pass = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);
  const TriggerPass = ({ children }: { asChild?: boolean; children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);
  const Item = ({
    children,
    onSelect,
    disabled,
  }: {
    children: React.ReactNode;
    onSelect?: (e: Event) => void;
    disabled?: boolean;
  }) =>
    React.createElement(
      "div",
      {
        role: "menuitem",
        "aria-disabled": disabled,
        onClick: () => {
          if (!disabled) onSelect?.(new Event("select"));
        },
      },
      children,
    );
  return {
    DropdownMenu: Pass,
    DropdownMenuContent: Pass,
    DropdownMenuTrigger: TriggerPass,
    DropdownMenuItem: Item,
  };
});

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
    mockSendEmailMutate.mockReset();
    mockMarkResolvedMutate.mockReset();
    mockExcludeMutate.mockReset();
    mockToastError.mockReset();
    mockToastSuccess.mockReset();
    mockSendEmailHookRef.current = {
      mutate: mockSendEmailMutate,
      isPending: false,
      variables: undefined,
    };
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
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("recommended email chip shows label for non-null type", () => {
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ recommended_email_type: "update_payment" })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    expect(screen.getAllByText("Update payment").length).toBeGreaterThan(0);
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

  it("Free tier disables all 4 controls with tier tooltip", () => {
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
      data: [makeRow({ recommended_email_type: "update_payment" })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    const tierTooltip = "Upgrade to Mid or Pro to enable email actions";
    const sendRecommended = screen.getByRole("button", { name: "Send recommended" });
    const sendSpecific = screen.getByRole("button", { name: "Send specific email" });
    const markResolved = screen.getByRole("button", { name: "Mark resolved" });
    const exclude = screen.getByRole("button", { name: "Exclude" });
    expect(sendRecommended).toBeDisabled();
    expect(sendSpecific).toBeDisabled();
    expect(markResolved).toBeDisabled();
    expect(exclude).toBeDisabled();
    expect(sendRecommended.getAttribute("title")).toBe(tierTooltip);
    expect(sendSpecific.getAttribute("title")).toBe(tierTooltip);
    expect(markResolved.getAttribute("title")).toBe(tierTooltip);
    expect(exclude.getAttribute("title")).toBe(tierTooltip);
  });

  it("Mid tier without DPA disables all 4 controls with DPA tooltip", () => {
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
      data: [makeRow({ recommended_email_type: "update_payment" })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    const dpaTooltip = "Sign the DPA to enable email sends";
    const sendRecommended = screen.getByRole("button", { name: "Send recommended" });
    const sendSpecific = screen.getByRole("button", { name: "Send specific email" });
    const markResolved = screen.getByRole("button", { name: "Mark resolved" });
    const exclude = screen.getByRole("button", { name: "Exclude" });
    expect(sendRecommended).toBeDisabled();
    expect(sendSpecific).toBeDisabled();
    expect(markResolved).toBeDisabled();
    expect(exclude).toBeDisabled();
    expect(sendRecommended.getAttribute("title")).toBe(dpaTooltip);
    expect(sendSpecific.getAttribute("title")).toBe(dpaTooltip);
    expect(markResolved.getAttribute("title")).toBe(dpaTooltip);
    expect(exclude.getAttribute("title")).toBe(dpaTooltip);
  });

  it("Mid tier with DPA accepted enables Send recommended only when recommendation present", () => {
    setMidTierWithDpa();
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ recommended_email_type: null })],
      isLoading: false,
    });
    const { unmount } = render(<FailedPaymentsList />, { wrapper: createWrapper() });
    const disabled = screen.getByRole("button", { name: "Send recommended" });
    expect(disabled).toBeDisabled();
    expect(disabled.getAttribute("title")).toBe("No recommendation available yet");
    unmount();

    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ recommended_email_type: "update_payment" })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    const enabled = screen.getByRole("button", { name: "Send recommended" });
    expect(enabled).not.toBeDisabled();
    expect(enabled.getAttribute("title")).toBeFalsy();
  });

  it("Send recommended button calls useSendEmail with row's recommended_email_type", () => {
    setMidTierWithDpa();
    const row = makeRow({ id: 99, subscriber_id: 11, recommended_email_type: "update_payment" });
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });

    fireEvent.click(screen.getByRole("button", { name: "Send recommended" }));
    expect(mockSendEmailMutate).toHaveBeenCalledTimes(1);
    expect(mockSendEmailMutate.mock.calls[0][0]).toEqual({
      subscriberId: 11,
      failureId: 99,
      emailType: "update_payment",
    });
  });

  it("dropdown lists three options in the correct order", () => {
    setMidTierWithDpa();
    const row = makeRow({ id: 12, subscriber_id: 5, recommended_email_type: null });
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });

    const items = screen.getAllByRole("menuitem");
    expect(items.map((el) => el.textContent)).toEqual([
      "Update payment",
      "Retry reminder",
      "Final notice",
    ]);
  });

  it.each([
    ["Update payment", "update_payment"],
    ["Retry reminder", "retry_reminder"],
    ["Final notice", "final_notice"],
  ])("dropdown menuitem %s dispatches send with type %s", (label, expectedType) => {
    setMidTierWithDpa();
    const row = makeRow({ id: 12, subscriber_id: 5, recommended_email_type: null });
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });

    fireEvent.click(screen.getByRole("menuitem", { name: label }));

    expect(mockSendEmailMutate).toHaveBeenCalledTimes(1);
    expect(mockSendEmailMutate.mock.calls[0][0]).toEqual({
      subscriberId: 5,
      failureId: 12,
      emailType: expectedType,
    });
  });

  it("Mark resolved button calls useMarkResolved", () => {
    setMidTierWithDpa();
    const row = makeRow({ subscriber_id: 22 });
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });

    fireEvent.click(screen.getByRole("button", { name: "Mark resolved" }));
    expect(mockMarkResolvedMutate).toHaveBeenCalledWith(22, expect.any(Object));
  });

  it("Exclude button calls useExcludeSubscriber", () => {
    setMidTierWithDpa();
    const row = makeRow({ subscriber_id: 33 });
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });

    fireEvent.click(screen.getByRole("button", { name: "Exclude" }));
    expect(mockExcludeMutate).toHaveBeenCalledWith(33, expect.any(Object));
  });

  it("Sending… label appears on the recommended button while mutation is pending", () => {
    setMidTierWithDpa();
    const row = makeRow({ subscriber_id: 1, id: 1, recommended_email_type: "update_payment" });
    mockSendEmailHookRef.current = {
      mutate: mockSendEmailMutate,
      isPending: true,
      variables: { subscriberId: 1, failureId: 1, emailType: "update_payment" },
    };
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });

    const btn = screen.getByRole("button", { name: "Send recommended" });
    expect(btn).toHaveTextContent("Sending…");
    expect(btn).toBeDisabled();
  });

  it("RATE_LIMITED error invokes toast.error with retryAfterSeconds", () => {
    setMidTierWithDpa();
    const row = makeRow({ subscriber_id: 1, id: 1, recommended_email_type: "update_payment" });
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });

    mockSendEmailMutate.mockImplementation((_vars, opts) => {
      const err = { code: "RATE_LIMITED", retryAfterSeconds: 42, message: "x" };
      opts?.onError?.(err);
    });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Send recommended" }));
    });

    expect(mockToastError).toHaveBeenCalledWith(
      "Rate limit reached. Try again in 42s.",
      { duration: 6000 },
    );
  });

  it("OPT_OUT error invokes toast.error with opt-out message", () => {
    setMidTierWithDpa();
    const row = makeRow({ subscriber_id: 1, id: 1, recommended_email_type: "update_payment" });
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });

    mockSendEmailMutate.mockImplementation((_vars, opts) => {
      opts?.onError?.({ code: "OPT_OUT", retryAfterSeconds: null, message: "x" });
    });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Send recommended" }));
    });
    expect(mockToastError).toHaveBeenCalledWith(
      "Subscriber has opted out of notifications.",
      { duration: 6000 },
    );
  });

  it("EXCLUDED error invokes toast.error with excluded message", () => {
    setMidTierWithDpa();
    const row = makeRow({ subscriber_id: 1, id: 1, recommended_email_type: "update_payment" });
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });

    mockSendEmailMutate.mockImplementation((_vars, opts) => {
      opts?.onError?.({ code: "EXCLUDED", retryAfterSeconds: null, message: "x" });
    });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Send recommended" }));
    });
    expect(mockToastError).toHaveBeenCalledWith(
      "Subscriber is excluded from automation.",
      { duration: 6000 },
    );
  });

  it("DPA_REQUIRED error invokes toast.error with infinite duration", () => {
    setMidTierWithDpa();
    const row = makeRow({ subscriber_id: 1, id: 1, recommended_email_type: "update_payment" });
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });

    mockSendEmailMutate.mockImplementation((_vars, opts) => {
      opts?.onError?.({ code: "DPA_REQUIRED", retryAfterSeconds: null, message: "x" });
    });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Send recommended" }));
    });
    expect(mockToastError).toHaveBeenCalledWith(
      "Sign the DPA to enable email sends.",
      { duration: Infinity },
    );
  });

  it("unknown error code falls back to err.message", () => {
    setMidTierWithDpa();
    const row = makeRow({ subscriber_id: 1, id: 1, recommended_email_type: "update_payment" });
    mockUseFailedPayments.mockReturnValue({ data: [row], isLoading: false });

    mockSendEmailMutate.mockImplementation((_vars, opts) => {
      opts?.onError?.({ code: "WHAT", retryAfterSeconds: null, message: "Server is on fire" });
    });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Send recommended" }));
    });
    expect(mockToastError).toHaveBeenCalledWith(
      "Server is on fire",
      { duration: 6000 },
    );
  });
});
