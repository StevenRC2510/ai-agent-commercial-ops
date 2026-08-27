import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatHeader } from "./ChatHeader";

// Spread rather than a literal `role=` attribute: jsx-a11y reads that as an ARIA role.
const renderHeader = (overrides: Partial<Parameters<typeof ChatHeader>[0]> = {}) => {
  const props = {
    brand: <span>Marca</span>,
    role: "operator" as const,
    disabled: false,
    onRoleChange: vi.fn(),
    onClear: vi.fn(),
    ...overrides,
  };
  return render(<ChatHeader {...props} />);
};

describe("ChatHeader", () => {
  it("shows the brand slot it was given rather than owning the identity", () => {
    renderHeader();

    expect(screen.getByText("Marca")).toBeInTheDocument();
  });

  it("offers the role group and the clear action", () => {
    renderHeader();

    expect(screen.getByRole("group", { name: /rol/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /limpiar/i })).toBeInTheDocument();
  });

  it("clears the conversation when asked", () => {
    const onClear = vi.fn();
    renderHeader({ onClear });

    fireEvent.click(screen.getByRole("button", { name: /limpiar/i }));

    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("locks both controls mid-request", () => {
    renderHeader({ disabled: true });

    expect(screen.getByRole("button", { name: /limpiar/i })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Supervisor" })).toBeDisabled();
  });

  // The band above xl was clipped because the hint appeared before it fit; it must not come back.
  it("reveals no extra prose at wide viewports", () => {
    renderHeader();

    expect(screen.queryByText(/reinicia la conversación/i)).not.toBeInTheDocument();
  });
});
