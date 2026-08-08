import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import type { CollectionTask } from "@/lib/collections/types";

import { CompleteTaskModal, validateCompleteTaskNotes } from "./complete-task-modal";

const completeCollectionTask = vi.fn();

vi.mock("@/lib/collections/api", () => ({
  completeCollectionTask: (...args: unknown[]) => completeCollectionTask(...args),
}));

const task: CollectionTask = {
  id: 9,
  customer: 1,
  customer_name: "Acme",
  customer_risk_status: "LOW",
  invoice: null,
  task_type: "CALL",
  status: "OPEN",
  priority: "MEDIUM",
  priority_score: 50,
  title: "Arama",
  description: "",
  due_date: "2026-07-31",
  assigned_to: null,
  overdue_balance: "100.00",
  overdue_days: 2,
  last_contact_at: null,
  payment_promise: null,
};

afterEach(() => {
  cleanup();
});

describe("validateCompleteTaskNotes", () => {
  it("requires non-empty trimmed notes", () => {
    expect(validateCompleteTaskNotes("")).toBe(false);
    expect(validateCompleteTaskNotes("  ")).toBe(false);
    expect(validateCompleteTaskNotes("ok")).toBe(true);
  });
});

describe("CompleteTaskModal", () => {
  beforeEach(() => {
    completeCollectionTask.mockReset();
  });

  it("blocks submit without notes", async () => {
    const user = userEvent.setup();
    const onDone = vi.fn();
    render(
      <ToastProvider>
        <CompleteTaskModal task={task} onClose={() => undefined} onDone={onDone} />
      </ToastProvider>,
    );
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    expect(completeCollectionTask).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
    expect(await screen.findByText("Görüşme notu zorunlu")).toBeInTheDocument();
  });

  it("submits outcome and notes", async () => {
    completeCollectionTask.mockResolvedValue({ ok: true, data: {} });
    const user = userEvent.setup();
    const onDone = vi.fn();
    render(
      <ToastProvider>
        <CompleteTaskModal task={task} onClose={() => undefined} onDone={onDone} />
      </ToastProvider>,
    );
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText(/^Not/), "Müşteri ödeyecek");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    expect(completeCollectionTask).toHaveBeenCalledWith(
      9,
      expect.objectContaining({
        outcome: "REACHED",
        outcome_notes: "Müşteri ödeyecek",
      }),
    );
  });

  it("shows promise fields when PROMISE_GIVEN selected", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <CompleteTaskModal task={task} onClose={() => undefined} onDone={() => undefined} />
      </ToastProvider>,
    );
    const dialog = screen.getByRole("dialog");
    await user.selectOptions(
      within(dialog).getByLabelText(/Görüşme sonucu/),
      "PROMISE_GIVEN",
    );
    expect(within(dialog).getByLabelText(/Söz tutarı/)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/Söz tarihi/)).toBeInTheDocument();
  });
});
