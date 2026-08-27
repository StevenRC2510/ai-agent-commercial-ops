import type { TurnEnvelope } from "../domain/conversation.types";

import type { FakeChatGateway, ScriptedTurn, WireTurn } from "./FakeChatGateway.types";
import { turnResponseSchema } from "./turnResponseSchema";

// Overrides use the backend's snake_case field names, not the domain's.
export const wireTurn = (overrides: WireTurn = {}): WireTurn => ({
  type: "message",
  text: "Listo.",
  trace_id: "trace-1",
  telemetry: { latency_ms: 1200, input_tokens: 800, output_tokens: 47, iterations: 1 },
  ...overrides,
});

/** The only test double in the frontend (ADR 0007), substituted at the port. */
export const createFakeChatGateway = (script: readonly ScriptedTurn[] = []): FakeChatGateway => {
  const remaining = [...script];
  const sendCalls: FakeChatGateway["sendCalls"] = [];
  const confirmCalls: FakeChatGateway["confirmCalls"] = [];

  // Validated against the same schema as the real adapter: a fake cannot invent a shape.
  const next = (): Promise<TurnEnvelope> => {
    const entry = remaining.shift();
    if (entry === undefined) {
      return Promise.reject(new Error("FakeChatGateway: the script ran out of turns"));
    }
    if (entry instanceof Error) return Promise.reject(entry);

    const parsed = turnResponseSchema.safeParse(entry);
    if (!parsed.success) {
      const detail = parsed.error.message;
      return Promise.reject(new Error(`FakeChatGateway: invalid scripted turn — ${detail}`));
    }
    return Promise.resolve(parsed.data);
  };

  return {
    sendCalls,
    confirmCalls,
    sendMessage: (input) => {
      sendCalls.push(input);
      return next();
    },
    confirmAction: (input) => {
      confirmCalls.push(input);
      return next();
    },
  };
};
