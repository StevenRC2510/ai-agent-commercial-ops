import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RoleSelector } from "./RoleSelector";

describe("RoleSelector", () => {
  it("shows both modes at once and marks the one in force", () => {
    render(<RoleSelector value="operator" disabled={false} onChange={vi.fn()} />);

    expect(screen.getByRole("radio", { name: "Operador" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Supervisor" })).not.toBeChecked();
  });

  it("is a labelled group, not a row of loose buttons", () => {
    render(<RoleSelector value="supervisor" disabled={false} onChange={vi.fn()} />);

    expect(screen.getByRole("group", { name: /rol/i })).toBeInTheDocument();
  });

  // The transcript announces the reset when it happens; the chrome must not carry it permanently.
  it("keeps no standing explanation of what switching does", () => {
    render(<RoleSelector value="operator" disabled={false} onChange={vi.fn()} />);

    expect(screen.queryByText(/reinicia la conversación/i)).not.toBeInTheDocument();
  });

  it("reports the role the user picked", () => {
    const onChange = vi.fn();
    render(<RoleSelector value="operator" disabled={false} onChange={onChange} />);

    fireEvent.click(screen.getByRole("radio", { name: "Supervisor" }));

    expect(onChange).toHaveBeenCalledWith("supervisor");
  });

  it("cannot be switched mid-request", () => {
    render(<RoleSelector value="supervisor" disabled onChange={vi.fn()} />);

    expect(screen.getByRole("radio", { name: "Operador" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Supervisor" })).toBeDisabled();
  });
});
