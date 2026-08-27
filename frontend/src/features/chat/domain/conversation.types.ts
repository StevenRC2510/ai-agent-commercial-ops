import type { Telemetry } from "./telemetry.types";

export type TurnType = "message" | "confirmation_required" | "error";

export type MessageAuthor = "user" | "agent" | "system";

export type MessageTone = "answer" | "denial";

/** One answer from the agent, whatever endpoint produced it (SPEC-2 §8). */
export interface TurnEnvelope {
  type: TurnType;
  text: string;
  traceId: string;
  pendingId: string | null;
  pendingSummary: string | null;
  reasonCode: string | null;
  telemetry: Telemetry | null;
}

/** A write the agent proposed, waiting for out-of-band consent. */
export interface PendingAction {
  id: string;
  summary: string;
}

export interface ChatMessage {
  id: string;
  author: MessageAuthor;
  text: string;
  tone?: MessageTone;
  traceId?: string;
  telemetry?: Telemetry;
}

export interface Conversation {
  readonly messages: readonly ChatMessage[];
  readonly pending: PendingAction | null;
}
