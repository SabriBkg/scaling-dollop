import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import React from "react";

import { BulkActionToolbar } from "@/components/dashboard/BulkActionToolbar";
import type { FailedPayment } from "@/types/failed_payment";

// Stub Base UI Dialog primitives so they render synchronously in jsdom.
vi.mock("@/components/ui/dialog", async () => {
  const Pass = ({ children, ...rest }: { children?: React.ReactNode } & Record<string, unknown>) =>
    React.createElement("div", rest as Record<string, unknown>, children);
  return {
    Dialog: ({
      open,
      children,
    }: {
      open?: boolean;
      children?: React.ReactNode;
      onOpenChange?: (next: boolean) => void;
    }) =>
      open ? React.createElement("div", { role: "dialog" }, children) : null,
    DialogContent: Pass,
    DialogDescription: Pass,
    DialogFooter: Pass,
    DialogHeader: Pass,
    DialogTitle: ({ children }: { children?: React.ReactNode }) =>
      React.createElement("h2", null, children),
  };
});

// Flatten Radix-style DropdownMenu primitives for jsdom.
vi.mock("@/components/ui/dropdown-menu", async () => {
  const Pass = ({ children }: { children: React.ReactNode }) =>
    React.createElement(React.Fragment, null, children);
  // Base UI's `render` prop receives an element that becomes the trigger;
  // clone it with children injected so aria-labels on the inner Button
  // stay queryable in jsdom.
  const TriggerPass = ({
    render: renderElement,
    children,
  }: {
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
    onClick,
    onSelect,
    disabled,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    onSelect?: () => void;
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
          onSelect?.();
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
    recommended_email_type: "update_payment",
    last_email_sent_at: null,
    payment_method_country: "FR",
    excluded_from_automation: false,
    geo_warning: false,
    ...overrides,
  };
}

const baseHandlers = () => ({
  onSendRecommended: vi.fn(),
  onSendSpecific: vi.fn(),
  onMarkResolved: vi.fn(),
  onExclude: vi.fn(),
  onDeselectAll: vi.fn(),
});

describe("BulkActionToolbar", () => {
  let handlers: ReturnType<typeof baseHandlers>;

  beforeEach(() => {
    handlers = baseHandlers();
  });

  it("renders nothing when selectedRows is empty", () => {
    render(<BulkActionToolbar selectedRows={[]} isPending={false} {...handlers} />);
    expect(screen.queryByRole("toolbar")).toBeNull();
  });

  it("renders toolbar with N selected and 4 buttons + deselect link", () => {
    render(
      <BulkActionToolbar
        selectedRows={[makeRow({ id: 1 }), makeRow({ id: 2 })]}
        isPending={false}
        {...handlers}
      />,
    );
    const toolbar = screen.getByRole("toolbar");
    expect(toolbar).toBeInTheDocument();
    expect(within(toolbar).getByText("2 rows selected")).toBeInTheDocument();
    // buttons are queryable by aria-label
    expect(within(toolbar).getByLabelText("Send recommended 2")).toBeInTheDocument();
    expect(within(toolbar).getByLabelText("Send specific email")).toBeInTheDocument();
    expect(within(toolbar).getByLabelText("Mark resolved 2")).toBeInTheDocument();
    expect(within(toolbar).getByLabelText("Exclude 2")).toBeInTheDocument();
    expect(within(toolbar).getByText("Deselect all")).toBeInTheDocument();
  });

  it("Send recommended is disabled when zero rows have a recommendation", () => {
    render(
      <BulkActionToolbar
        selectedRows={[
          makeRow({ id: 1, recommended_email_type: null }),
          makeRow({ id: 2, recommended_email_type: null }),
        ]}
        isPending={false}
        {...handlers}
      />,
    );
    const btn = screen.getByLabelText("Send recommended 2") as HTMLButtonElement;
    expect(btn).toBeDisabled();
  });

  it("clicking Send recommended opens confirmation dialog with rollup + skipped", () => {
    render(
      <BulkActionToolbar
        selectedRows={[
          makeRow({ id: 1, recommended_email_type: "update_payment" }),
          makeRow({ id: 2, recommended_email_type: "update_payment" }),
          makeRow({ id: 3, recommended_email_type: null }),
        ]}
        isPending={false}
        {...handlers}
      />,
    );
    fireEvent.click(screen.getByLabelText("Send recommended 3"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Send 2 dunning emails?")).toBeInTheDocument();
    expect(within(dialog).getByText(/Update Payment ×2/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Skipped \(no recommendation\): 1/)).toBeInTheDocument();
  });

  it("confirming Send recommended dispatches with filtered selections and skipped", () => {
    render(
      <BulkActionToolbar
        selectedRows={[
          makeRow({ id: 1, subscriber_id: 11, recommended_email_type: "update_payment" }),
          makeRow({ id: 3, subscriber_id: 13, recommended_email_type: null }),
        ]}
        isPending={false}
        {...handlers}
      />,
    );
    fireEvent.click(screen.getByLabelText("Send recommended 2"));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByText("Send all"));
    expect(handlers.onSendRecommended).toHaveBeenCalledTimes(1);
    const [selections, skipped] = handlers.onSendRecommended.mock.calls[0];
    expect(selections).toEqual([{
      subscriber_id: 11,
      failure_id: 1,
      email_type: "update_payment",
    }]);
    expect(skipped).toHaveLength(1);
    expect(skipped[0].id).toBe(3);
  });

  it("clicking Cancel does not dispatch", () => {
    render(
      <BulkActionToolbar
        selectedRows={[makeRow({ id: 1, recommended_email_type: "update_payment" })]}
        isPending={false}
        {...handlers}
      />,
    );
    fireEvent.click(screen.getByLabelText("Send recommended 1"));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByText("Cancel"));
    expect(handlers.onSendRecommended).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Send specific dropdown picks an option, dialog opens, confirm dispatches all rows mapped", () => {
    render(
      <BulkActionToolbar
        selectedRows={[
          makeRow({ id: 1, subscriber_id: 11 }),
          makeRow({ id: 2, subscriber_id: 12 }),
        ]}
        isPending={false}
        {...handlers}
      />,
    );
    fireEvent.click(screen.getByText("Final notice"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Send 2 Final Notice emails?")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByText("Send all"));
    expect(handlers.onSendSpecific).toHaveBeenCalledTimes(1);
    const [selections, emailType] = handlers.onSendSpecific.mock.calls[0];
    expect(emailType).toBe("final_notice");
    expect(selections).toEqual([
      { subscriber_id: 11, failure_id: 1, email_type: "final_notice" },
      { subscriber_id: 12, failure_id: 2, email_type: "final_notice" },
    ]);
  });

  it("Send specific filters out non-active rows client-side", () => {
    render(
      <BulkActionToolbar
        selectedRows={[
          makeRow({ id: 1, subscriber_id: 11, subscriber_status: "active" }),
          makeRow({ id: 2, subscriber_id: 12, subscriber_status: "recovered" }),
        ]}
        isPending={false}
        {...handlers}
      />,
    );
    fireEvent.click(screen.getByText("Update payment"));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByText("Send all"));
    const [selections] = handlers.onSendSpecific.mock.calls[0];
    expect(selections).toHaveLength(1);
    expect(selections[0].subscriber_id).toBe(11);
  });

  it("Mark resolved opens confirmation dialog with subscriber list", () => {
    render(
      <BulkActionToolbar
        selectedRows={[makeRow({ id: 1 }), makeRow({ id: 2 })]}
        isPending={false}
        {...handlers}
      />,
    );
    fireEvent.click(screen.getByLabelText("Mark resolved 2"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Mark 2 as resolved?")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByText("Mark resolved"));
    expect(handlers.onMarkResolved).toHaveBeenCalledTimes(1);
    expect(handlers.onMarkResolved.mock.calls[0][0]).toHaveLength(2);
  });

  it("Exclude opens confirmation dialog with subscriber list", () => {
    render(
      <BulkActionToolbar
        selectedRows={[makeRow({ id: 1 }), makeRow({ id: 2 })]}
        isPending={false}
        {...handlers}
      />,
    );
    fireEvent.click(screen.getByLabelText("Exclude 2"));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Exclude 2 from future recommendations?")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByText("Exclude all"));
    expect(handlers.onExclude).toHaveBeenCalledTimes(1);
  });

  it("Deselect all link calls onDeselectAll", () => {
    render(
      <BulkActionToolbar
        selectedRows={[makeRow({ id: 1 })]}
        isPending={false}
        {...handlers}
      />,
    );
    fireEvent.click(screen.getByText("Deselect all"));
    expect(handlers.onDeselectAll).toHaveBeenCalledTimes(1);
  });

  it("selection-count line has aria-live=polite", () => {
    render(
      <BulkActionToolbar
        selectedRows={[makeRow({ id: 1 })]}
        isPending={false}
        {...handlers}
      />,
    );
    const count = screen.getByText("1 row selected");
    expect(count.getAttribute("aria-live")).toBe("polite");
  });

  it("disables all toolbar buttons when isPending=true", () => {
    render(
      <BulkActionToolbar
        selectedRows={[makeRow({ id: 1 })]}
        isPending={true}
        {...handlers}
      />,
    );
    expect((screen.getByLabelText("Send recommended 1") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText("Send specific email") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText("Mark resolved 1") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText("Exclude 1") as HTMLButtonElement).disabled).toBe(true);
  });
});
