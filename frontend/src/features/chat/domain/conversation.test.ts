import { describe, expect, it } from "vitest";

import { EMPTY_CONVERSATION, withSystemMessage, withTurn, withUserMessage } from "./conversation";
import type { TurnEnvelope } from "./conversation.types";

const envelope = (overrides: Partial<TurnEnvelope> = {}): TurnEnvelope => ({
  type: "message",
  text: "Listo.",
  traceId: "trace-1",
  pendingId: null,
  pendingSummary: null,
  reasonCode: null,
  telemetry: null,
  ...overrides,
});

describe("conversation", () => {
  it("gives every appended message a distinct id", () => {
    const conversation = withTurn(withUserMessage(EMPTY_CONVERSATION, "hola"), envelope());

    expect(conversation.messages.map((message) => message.id)).toEqual(["0", "1"]);
    expect(conversation.messages.map((message) => message.author)).toEqual(["user", "agent"]);
  });

  it("owes consent after a confirmation_required turn", () => {
    const conversation = withTurn(
      EMPTY_CONVERSATION,
      envelope({
        type: "confirmation_required",
        pendingId: "pending-9",
        pendingSummary: "Orden #3: de en proceso a entregada",
      }),
    );

    expect(conversation.pending).toEqual({
      id: "pending-9",
      summary: "Orden #3: de en proceso a entregada",
    });
  });

  it("marks a refused turn as a denial and an ordinary one as an answer", () => {
    const refused = withTurn(EMPTY_CONVERSATION, envelope({ type: "error", reasonCode: "denied" }));
    const answered = withTurn(EMPTY_CONVERSATION, envelope());

    expect(refused.messages[0]?.tone).toBe("denial");
    expect(answered.messages[0]?.tone).toBe("answer");
  });

  it("clears the pending action on any turn that is not a new request for consent", () => {
    const owed = withTurn(
      EMPTY_CONVERSATION,
      envelope({ type: "confirmation_required", pendingId: "pending-9" }),
    );

    expect(withTurn(owed, envelope({ text: "Cambio aplicado." })).pending).toBeNull();
  });

  it("never mutates the conversation it is given", () => {
    const before = withUserMessage(EMPTY_CONVERSATION, "hola");
    withSystemMessage(before, "Sesión reiniciada.");

    expect(before.messages).toHaveLength(1);
    expect(EMPTY_CONVERSATION.messages).toHaveLength(0);
  });
});
