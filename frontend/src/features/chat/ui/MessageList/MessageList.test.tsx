import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "../../domain/conversation.types";

import { MessageList } from "./MessageList";

const MESSAGES: ChatMessage[] = [
  { id: "0", author: "user", text: "¿cuántas órdenes hay en proceso?" },
  { id: "1", author: "agent", text: "Hay 4 órdenes en proceso.", traceId: "trace-1" },
];

describe("MessageList", () => {
  it("offers the empty state when the conversation has not started", () => {
    render(<MessageList messages={[]} isThinking={false} onPickExample={vi.fn()} />);

    expect(screen.getByText(/órdenes, inventario y clientes/i)).toBeInTheDocument();
  });

  it("renders the conversation inside a live region", () => {
    render(<MessageList messages={MESSAGES} isThinking={false} onPickExample={vi.fn()} />);

    expect(screen.getByRole("log")).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText("Hay 4 órdenes en proceso.")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("announces that a request is in flight", () => {
    render(<MessageList messages={MESSAGES} isThinking onPickExample={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent(/pensando/i);
  });
});
