import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ChatMessage } from "../../domain/conversation.types";

import { Message } from "./Message";

const INJECTION = '<img src=x onerror=alert(1)><script>alert("xss")</script>';

const agentMessage = (overrides: Partial<ChatMessage> = {}): ChatMessage => ({
  id: "1",
  author: "agent",
  text: "Listo.",
  traceId: "trace-abc",
  telemetry: { latencyMs: 1234, inputTokens: 800, outputTokens: 47, iterations: 1 },
  ...overrides,
});

describe("Message", () => {
  // SPEC-2 §9.3: agent text is attacker-influenceable through seeded data.
  it("renders markup in the agent text as visible text and never executes it", () => {
    const { container } = render(<Message message={agentMessage({ text: INJECTION })} />);

    expect(screen.getByText(INJECTION)).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.innerHTML).toContain("&lt;img");
  });

  it("shows the trace id and the telemetry under an agent answer", () => {
    render(<Message message={agentMessage()} />);

    expect(screen.getByText(/trace-abc/)).toBeInTheDocument();
    expect(screen.getByText(/1\.2s · 847 tok/)).toBeInTheDocument();
  });

  it("labels a denial so it never reads as an ordinary answer", () => {
    render(
      <Message
        message={agentMessage({ tone: "denial", text: "Tu rol no permite cambiar una orden." })}
      />,
    );

    expect(screen.getByText(/denegada/i)).toBeInTheDocument();
    expect(screen.getByText(/tu rol no permite/i)).toBeInTheDocument();
  });

  it("shows no telemetry line for a message that carries none", () => {
    render(<Message message={{ id: "2", author: "user", text: "hola" }} />);

    expect(screen.getByText("hola")).toBeInTheDocument();
    expect(screen.queryByText(/tok/)).not.toBeInTheDocument();
  });
});
