import type {
  ChatMessage,
  Conversation,
  MessageTone,
  PendingAction,
  TurnEnvelope,
} from "./conversation.types";

export const EMPTY_CONVERSATION: Conversation = Object.freeze({ messages: [], pending: null });

/** Append-only, so the position of a message is a stable identity for it. */
const append = (conversation: Conversation, message: Omit<ChatMessage, "id">): Conversation => {
  const entry: ChatMessage = { ...message, id: String(conversation.messages.length) };
  return { ...conversation, messages: [...conversation.messages, entry] };
};

export const withUserMessage = (conversation: Conversation, text: string): Conversation =>
  append(conversation, { author: "user", text });

export const withSystemMessage = (conversation: Conversation, text: string): Conversation =>
  append(conversation, { author: "system", text });

const toneOf = (envelope: TurnEnvelope): MessageTone =>
  envelope.type === "error" || envelope.reasonCode ? "denial" : "answer";

const pendingOf = (envelope: TurnEnvelope): PendingAction | null => {
  if (envelope.type !== "confirmation_required" || !envelope.pendingId) return null;
  return { id: envelope.pendingId, summary: envelope.pendingSummary ?? envelope.text };
};

export const withTurn = (conversation: Conversation, envelope: TurnEnvelope): Conversation => {
  const spoken = append(conversation, {
    author: "agent",
    text: envelope.text,
    tone: toneOf(envelope),
    traceId: envelope.traceId,
    ...(envelope.telemetry ? { telemetry: envelope.telemetry } : {}),
  });
  return { ...spoken, pending: pendingOf(envelope) };
};
