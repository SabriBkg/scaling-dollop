import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ReviewQueuePage from "@/app/(dashboard)/review-queue/page";

const mockPendingActions = vi.fn();
const mockBatchMutate = vi.fn();
const mockExcludeMutate = vi.fn();

vi.mock("@/hooks/usePendingActions", () => ({
  usePendingActions: () => mockPendingActions(),
}));

vi.mock("@/hooks/useBatchAction", () => ({
  useBatchAction: () => ({
    mutate: mockBatchMutate,
    isPending: false,
  }),
}));

vi.mock("@/hooks/useExcludeSubscriber", () => ({
  useExcludeSubscriber: () => ({
    mutate: mockExcludeMutate,
    isPending: false,
  }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
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

const sampleActions = [
  {
    id: 1,
    subscriber_name: "alice@example.com",
    decline_reason: "Insufficient funds",
    recommended_action: "retry_notify",
    amount_cents: 5000,
    created_at: "2026-04-14T12:00:00Z",
    failure_id: 10,
    subscriber_id: 100,
  },
  {
    id: 2,
    subscriber_name: "bob@example.com",
    decline_reason: "Card expired",
    recommended_action: "notify_only",
    amount_cents: 3000,
    created_at: "2026-04-14T11:00:00Z",
    failure_id: 11,
    subscriber_id: 101,
  },
];

describe("ReviewQueuePage", () => {
  beforeEach(() => {
    mockPendingActions.mockReset();
    mockBatchMutate.mockReset();
    mockExcludeMutate.mockReset();
  });

  it("renders pending actions with correct data", () => {
    mockPendingActions.mockReturnValue({
      data: sampleActions,
      isLoading: false,
    });

    render(<ReviewQueuePage />, { wrapper: createWrapper() });
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("bob@example.com")).toBeInTheDocument();
    expect(screen.getByText("Insufficient funds")).toBeInTheDocument();
    expect(screen.getByText("Card expired")).toBeInTheDocument();
  });

  it("pre-selects all rows on load", () => {
    mockPendingActions.mockReturnValue({
      data: sampleActions,
      isLoading: false,
    });

    render(<ReviewQueuePage />, { wrapper: createWrapper() });
    // Toolbar should show 2 selected
    expect(screen.getByText("2 subscribers selected")).toBeInTheDocument();
  });

  it("shows toolbar on selection, hides on deselect all", async () => {
    mockPendingActions.mockReturnValue({
      data: sampleActions,
      isLoading: false,
    });

    render(<ReviewQueuePage />, { wrapper: createWrapper() });
    expect(screen.getByText("Apply recommended actions")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Deselect all"));
    expect(screen.queryByText("Apply recommended actions")).not.toBeInTheDocument();
  });

  it("calls batch mutation on approve", () => {
    mockPendingActions.mockReturnValue({
      data: sampleActions,
      isLoading: false,
    });

    render(<ReviewQueuePage />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByText("Apply recommended actions"));

    expect(mockBatchMutate).toHaveBeenCalledWith(
      expect.arrayContaining([1, 2]),
      expect.any(Object)
    );
  });

  it("shows exclusion confirmation dialog", () => {
    mockPendingActions.mockReturnValue({
      data: sampleActions,
      isLoading: false,
    });

    render(<ReviewQueuePage />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByText("Exclude from automation"));

    expect(
      screen.getByText(
        "This subscriber will not receive automated retries or notifications."
      )
    ).toBeInTheDocument();
  });

  it("renders zero-state when no actions", () => {
    mockPendingActions.mockReturnValue({
      data: [],
      isLoading: false,
    });

    render(<ReviewQueuePage />, { wrapper: createWrapper() });
    expect(
      screen.getByText(
        "Nothing needs your eyes right now. Approved items and automated recoveries are handled."
      )
    ).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockPendingActions.mockReturnValue({
      data: undefined,
      isLoading: true,
    });

    render(<ReviewQueuePage />, { wrapper: createWrapper() });
    expect(screen.getByText("Review Queue")).toBeInTheDocument();
  });
});
