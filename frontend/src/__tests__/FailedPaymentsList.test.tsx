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
  mockToastWarning,
  mockSendEmailHookRef,
  mockBatchSendMutate,
  mockBatchSendHookRef,
  mockMarkResolvedFanoutRun,
  mockExcludeFanoutRun,
  mockBulkFanoutHookRef,
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
    mockToastWarning: vi.fn(),
    mockSendEmailHookRef: { current: { mutate: vi.fn(), isPending: false, variables: undefined as unknown } },
    mockBatchSendMutate: vi.fn(),
    mockBatchSendHookRef: { current: { mutate: vi.fn(), isPending: false } },
    mockMarkResolvedFanoutRun: vi.fn(),
    mockExcludeFanoutRun: vi.fn(),
    mockBulkFanoutHookRef: {
      current: {
        markResolved: { run: vi.fn(), isPending: false, lastResult: null },
        exclude: { run: vi.fn(), isPending: false, lastResult: null },
      },
    },
  };
  refs.mockSendEmailHookRef.current.mutate = refs.mockSendEmailMutate;
  refs.mockBatchSendHookRef.current.mutate = refs.mockBatchSendMutate;
  refs.mockBulkFanoutHookRef.current.markResolved.run = refs.mockMarkResolvedFanoutRun;
  refs.mockBulkFanoutHookRef.current.exclude.run = refs.mockExcludeFanoutRun;
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
  toast: { error: mockToastError, success: mockToastSuccess, warning: mockToastWarning },
}));

vi.mock("@/hooks/useBatchSendEmail", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/useBatchSendEmail")>(
    "@/hooks/useBatchSendEmail",
  );
  return {
    ...actual,
    useBatchSendEmail: () => mockBatchSendHookRef.current,
  };
});

vi.mock("@/hooks/useBulkFanout", () => ({
  useBulkFanout: (endpoint: string) =>
    endpoint === "mark-resolved"
      ? mockBulkFanoutHookRef.current.markResolved
      : mockBulkFanoutHookRef.current.exclude,
}));

// Radix DropdownMenu is hard to drive via fireEvent in jsdom (it uses an
// internal pointer-event lifecycle to fire onSelect). Replace with a flat
// passthrough so menuitem clicks call onSelect directly.
vi.mock("@/components/ui/dropdown-menu", async () => {
  const React = await import("react");
  const Pass = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);
  // Trigger: legacy asChild pattern just renders children. Base UI's
  // `render` prop receives a trigger element — clone it with children
  // injected so aria-labels stay queryable.
  const TriggerPass = ({
    render: renderElement,
    children,
  }: {
    asChild?: boolean;
    render?: React.ReactElement;
    children: React.ReactNode;
  }) => {
    if (renderElement) {
      return React.cloneElement(renderElement, undefined, children);
    }
    return React.createElement(React.Fragment, null, children);
  };
  const Item = ({
    children,
    onSelect,
    onClick,
    disabled,
  }: {
    children: React.ReactNode;
    onSelect?: (e: Event) => void;
    onClick?: () => void;
    disabled?: boolean;
  }) =>
    React.createElement(
      "div",
      {
        role: "menuitem",
        "aria-disabled": disabled,
        onClick: () => {
          if (disabled) return;
          onClick?.();
          onSelect?.(new Event("select"));
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

vi.mock("@/components/ui/dialog", async () => {
  const React = await import("react");
  const Pass = ({
    children,
    ...rest
  }: { children?: React.ReactNode } & Record<string, unknown>) =>
    React.createElement("div", rest as Record<string, unknown>, children);
  return {
    Dialog: ({
      open,
      children,
    }: {
      open?: boolean;
      onOpenChange?: (next: boolean) => void;
      children?: React.ReactNode;
    }) => (open ? React.createElement("div", { role: "dialog" }, children) : null),
    DialogContent: Pass,
    DialogDescription: Pass,
    DialogFooter: Pass,
    DialogHeader: Pass,
    DialogTitle: ({ children }: { children?: React.ReactNode }) =>
      React.createElement("h2", null, children),
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
    mockBatchSendMutate.mockReset();
    mockMarkResolvedFanoutRun.mockReset();
    mockExcludeFanoutRun.mockReset();
    mockToastError.mockReset();
    mockToastSuccess.mockReset();
    mockToastWarning.mockReset();
    mockSendEmailHookRef.current = {
      mutate: mockSendEmailMutate,
      isPending: false,
      variables: undefined,
    };
    mockBatchSendHookRef.current = {
      mutate: mockBatchSendMutate,
      isPending: false,
    };
    mockBulkFanoutHookRef.current = {
      markResolved: { run: mockMarkResolvedFanoutRun, isPending: false, lastResult: null },
      exclude: { run: mockExcludeFanoutRun, isPending: false, lastResult: null },
    };
    mockMarkResolvedFanoutRun.mockResolvedValue({
      succeeded: 0,
      failed: 0,
      total: 0,
      failures: [],
    });
    mockExcludeFanoutRun.mockResolvedValue({
      succeeded: 0,
      failed: 0,
      total: 0,
      failures: [],
    });
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

  // ---------- Story 3.4 v1 — bulk selection + toolbar ----------

  it("renders leading checkbox column for paid Mid-tier with DPA accepted", () => {
    setMidTierWithDpa();
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ id: 1 })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    expect(
      screen.getByLabelText("Select row for alice@example.com"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Select all visible rows")).toBeInTheDocument();
  });

  it("selecting a row reveals BulkActionToolbar", () => {
    setMidTierWithDpa();
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ id: 1 })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    expect(screen.queryByRole("toolbar")).toBeNull();
    fireEvent.click(screen.getByLabelText("Select row for alice@example.com"));
    expect(screen.getByRole("toolbar")).toBeInTheDocument();
  });

  it("Free-tier checkboxes are disabled with tier tooltip and toolbar never appears", () => {
    mockUseAccount.mockReturnValue({
      data: { id: 1, tier: "free", dpa_accepted: false },
      isLoading: false,
    });
    mockUseDpaGate.mockReturnValue({
      dpaAccepted: false, loading: false, sendDisabled: true,
      tooltip: "Sign the DPA to enable email sends", activatePath: "/activate",
    });
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ id: 1 })],
      isLoading: false,
    });
    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    const cb = screen.getByLabelText("Select row for alice@example.com");
    // Base UI's Checkbox surfaces disabled via aria-disabled (not the HTML attr).
    expect(cb.getAttribute("aria-disabled")).toBe("true");
    expect(cb.getAttribute("title")).toBe("Upgrade to Mid or Pro to enable email actions");
    expect(
      screen.getByLabelText("Select all visible rows").getAttribute("aria-disabled"),
    ).toBe("true");
    fireEvent.click(cb);
    expect(screen.queryByRole("toolbar")).toBeNull();
  });

  it("Send recommended dispatches via useBatchSendEmail with filtered selections", () => {
    setMidTierWithDpa();
    const r1 = makeRow({ id: 1, subscriber_id: 11, recommended_email_type: "update_payment" });
    const r2 = makeRow({ id: 2, subscriber_id: 12, recommended_email_type: "update_payment" });
    const r3 = makeRow({ id: 3, subscriber_id: 13, recommended_email_type: null });
    mockUseFailedPayments.mockReturnValue({ data: [r1, r2, r3], isLoading: false });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText("Select all visible rows"));
    const toolbar = screen.getByRole("toolbar");
    fireEvent.click(within(toolbar).getByLabelText("Send recommended 3"));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByText("Send all"));

    expect(mockBatchSendMutate).toHaveBeenCalledTimes(1);
    expect(mockBatchSendMutate.mock.calls[0][0]).toEqual([
      { subscriber_id: 11, failure_id: 1, email_type: "update_payment" },
      { subscriber_id: 12, failure_id: 2, email_type: "update_payment" },
    ]);
  });

  it("Mark resolved bulk fans out via useBulkFanout(mark-resolved)", async () => {
    setMidTierWithDpa();
    const r1 = makeRow({ id: 1, subscriber_id: 11 });
    const r2 = makeRow({ id: 2, subscriber_id: 12 });
    mockUseFailedPayments.mockReturnValue({ data: [r1, r2], isLoading: false });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText("Select all visible rows"));
    const toolbar = screen.getByRole("toolbar");
    fireEvent.click(within(toolbar).getByLabelText("Mark resolved 2"));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByText("Mark resolved"));

    expect(mockMarkResolvedFanoutRun).toHaveBeenCalledWith([11, 12]);
    expect(mockExcludeFanoutRun).not.toHaveBeenCalled();
  });

  it("Exclude bulk fans out via useBulkFanout(exclude)", () => {
    setMidTierWithDpa();
    const r1 = makeRow({ id: 1, subscriber_id: 11 });
    const r2 = makeRow({ id: 2, subscriber_id: 12 });
    mockUseFailedPayments.mockReturnValue({ data: [r1, r2], isLoading: false });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText("Select all visible rows"));
    const toolbar = screen.getByRole("toolbar");
    fireEvent.click(within(toolbar).getByLabelText("Exclude 2"));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByText("Exclude all"));

    expect(mockExcludeFanoutRun).toHaveBeenCalledWith([11, 12]);
    expect(mockMarkResolvedFanoutRun).not.toHaveBeenCalled();
  });

  it("Successful batch surfaces toast.success and clears selection", () => {
    setMidTierWithDpa();
    const r1 = makeRow({ id: 1, subscriber_id: 11, recommended_email_type: "update_payment" });
    mockUseFailedPayments.mockReturnValue({ data: [r1], isLoading: false });

    mockBatchSendMutate.mockImplementation((_vars, opts) => {
      opts?.onSuccess?.({ queued: 1, failed: 0, failures: [], selections_total: 1 });
    });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText("Select row for alice@example.com"));
    const toolbar = screen.getByRole("toolbar");
    fireEvent.click(within(toolbar).getByLabelText("Send recommended 1"));
    fireEvent.click(within(screen.getByRole("dialog")).getByText("Send all"));

    expect(mockToastSuccess).toHaveBeenCalledWith("Queued 1 dunning email.");
    // Selection cleared → toolbar gone.
    expect(screen.queryByRole("toolbar")).toBeNull();
  });

  it("Partial batch failure surfaces toast.warning with count breakdown", () => {
    setMidTierWithDpa();
    const r1 = makeRow({ id: 1, subscriber_id: 11, recommended_email_type: "update_payment" });
    const r2 = makeRow({ id: 2, subscriber_id: 12, recommended_email_type: "update_payment" });
    mockUseFailedPayments.mockReturnValue({ data: [r1, r2], isLoading: false });

    mockBatchSendMutate.mockImplementation((_vars, opts) => {
      opts?.onSuccess?.({
        queued: 1, failed: 1, selections_total: 2,
        failures: [{ subscriber_id: 12, failure_id: 2, code: "OPT_OUT", message: "x" }],
      });
    });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText("Select all visible rows"));
    fireEvent.click(within(screen.getByRole("toolbar")).getByLabelText("Send recommended 2"));
    fireEvent.click(within(screen.getByRole("dialog")).getByText("Send all"));

    expect(mockToastWarning).toHaveBeenCalledWith(
      "Queued 1 of 2. 1 failed.",
      { duration: 8000 },
    );
  });

  it("429 batch error surfaces toast.error with retry-after seconds", () => {
    setMidTierWithDpa();
    const r1 = makeRow({ id: 1, subscriber_id: 11, recommended_email_type: "update_payment" });
    mockUseFailedPayments.mockReturnValue({ data: [r1], isLoading: false });

    mockBatchSendMutate.mockImplementation((_vars, opts) => {
      opts?.onError?.({ code: "RATE_LIMITED", retryAfterSeconds: 42, message: "x" });
    });

    render(<FailedPaymentsList />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText("Select row for alice@example.com"));
    fireEvent.click(within(screen.getByRole("toolbar")).getByLabelText("Send recommended 1"));
    fireEvent.click(within(screen.getByRole("dialog")).getByText("Send all"));

    expect(mockToastError).toHaveBeenCalledWith(
      "Rate limit reached on bulk send. Try again in 42s.",
      { duration: 6000 },
    );
  });

  it("sort change clears stale selectedIds (toolbar disappears when refetch drops the row)", () => {
    setMidTierWithDpa();
    const initial = [
      makeRow({ id: 1, subscriber_id: 11 }),
      makeRow({ id: 2, subscriber_id: 12 }),
    ];
    mockUseFailedPayments.mockReturnValue({ data: initial, isLoading: false });

    const { rerender } = render(<FailedPaymentsList />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByLabelText("Select all visible rows"));
    expect(screen.getByRole("toolbar")).toBeInTheDocument();

    // Sort/refetch returns a different row set — the previously-selected ids
    // (1, 2) are no longer in `data`. selectedIds should prune; toolbar hides.
    mockUseFailedPayments.mockReturnValue({
      data: [makeRow({ id: 99, subscriber_id: 99 })],
      isLoading: false,
    });
    rerender(<FailedPaymentsList />);
    expect(screen.queryByRole("toolbar")).toBeNull();
  });
});
