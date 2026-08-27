import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EXAMPLE_PROMPTS } from "./EmptyState.constants";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("says what the assistant can do", () => {
    render(<EmptyState onPick={vi.fn()} />);

    expect(screen.getByText(/órdenes, inventario y clientes/i)).toBeInTheDocument();
  });

  it("offers every example as something the user can press", () => {
    render(<EmptyState onPick={vi.fn()} />);

    EXAMPLE_PROMPTS.forEach((prompt) => {
      expect(screen.getByRole("button", { name: prompt })).toBeInTheDocument();
    });
  });

  it("sends the example the user picked, verbatim", () => {
    const onPick = vi.fn();
    render(<EmptyState onPick={onPick} />);

    const [first] = EXAMPLE_PROMPTS;
    fireEvent.click(screen.getByRole("button", { name: first }));

    expect(onPick).toHaveBeenCalledWith(first);
  });
});
