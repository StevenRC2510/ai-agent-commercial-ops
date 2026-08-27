import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Composer } from "./Composer";

const type = (text: string) => {
  fireEvent.change(screen.getByLabelText(/mensaje/i), { target: { value: text } });
};

describe("Composer", () => {
  it("sends the draft and clears the field", () => {
    const onSend = vi.fn();
    render(<Composer disabled={false} onSend={onSend} />);

    type("¿cuántas órdenes hay?");
    fireEvent.click(screen.getByRole("button", { name: /enviar/i }));

    expect(onSend).toHaveBeenCalledWith("¿cuántas órdenes hay?");
    expect(screen.getByLabelText(/mensaje/i)).toHaveValue("");
  });

  it("refuses to send an empty draft", () => {
    const onSend = vi.fn();
    render(<Composer disabled={false} onSend={onSend} />);

    type("   ");
    fireEvent.click(screen.getByRole("button", { name: /enviar/i }));

    expect(onSend).not.toHaveBeenCalled();
  });

  it("blocks the field entirely when the conversation is not the user's turn", () => {
    render(<Composer disabled onSend={vi.fn()} />);

    expect(screen.getByLabelText(/mensaje/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /enviar/i })).toBeDisabled();
  });

  it("sends on Enter", () => {
    const onSend = vi.fn();
    render(<Composer disabled={false} onSend={onSend} />);

    type("hola");
    fireEvent.keyDown(screen.getByLabelText(/mensaje/i), { key: "Enter" });

    expect(onSend).toHaveBeenCalledWith("hola");
  });

  it("makes a newline on Shift+Enter instead of sending", () => {
    const onSend = vi.fn();
    render(<Composer disabled={false} onSend={onSend} />);

    type("primera línea");
    fireEvent.keyDown(screen.getByLabelText(/mensaje/i), { key: "Enter", shiftKey: true });

    expect(onSend).not.toHaveBeenCalled();
  });

  it("says how to send and how to break a line", () => {
    render(<Composer disabled={false} onSend={vi.fn()} />);

    expect(screen.getByText(/shift/i)).toBeInTheDocument();
  });

  it("takes focus as soon as it becomes usable again", () => {
    const { rerender } = render(<Composer disabled onSend={vi.fn()} />);
    expect(screen.getByLabelText(/mensaje/i)).not.toHaveFocus();

    rerender(<Composer disabled={false} onSend={vi.fn()} />);

    expect(screen.getByLabelText(/mensaje/i)).toHaveFocus();
  });
});
