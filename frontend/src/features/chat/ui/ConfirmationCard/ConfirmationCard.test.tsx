import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmationCard } from "./ConfirmationCard";

const SUMMARY = "Orden #3: de en proceso a entregada";

const renderCard = (isConfirming = false) => {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(
    <ConfirmationCard
      summary={SUMMARY}
      isConfirming={isConfirming}
      onConfirm={onConfirm}
      onCancel={onCancel}
    />,
  );
  return { onConfirm, onCancel };
};

describe("ConfirmationCard", () => {
  it("announces the pending action and shows what will be executed", () => {
    renderCard();

    expect(screen.getByRole("alert")).toHaveAttribute("aria-live", "assertive");
    expect(screen.getByText(SUMMARY)).toBeInTheDocument();
  });

  it("moves focus to Confirmar so the decision is reachable by keyboard", () => {
    renderCard();

    expect(screen.getByRole("button", { name: /confirmar/i })).toHaveFocus();
  });

  it("fires onConfirm when Confirmar is pressed", () => {
    const { onConfirm, onCancel } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: /confirmar/i }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("fires onCancel when Cancelar is pressed", () => {
    const { onConfirm, onCancel } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: /cancelar/i }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("disables both buttons while the confirmation is in flight", () => {
    renderCard(true);

    expect(screen.getByRole("button", { name: /confirmar/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /cancelar/i })).toBeDisabled();
  });
});
