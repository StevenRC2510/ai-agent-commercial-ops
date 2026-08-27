import type { TurnEnvelope } from "../domain/conversation.types";
import type { UserRole } from "../domain/roles.types";

/** Who is asking. Identity and authorization stay separate on purpose. */
export interface ChatIdentity {
  actor: string;
  role: UserRole;
}

export interface SendMessageInput {
  message: string;
  sessionId: string;
  identity: ChatIdentity;
}

export interface ConfirmActionInput {
  pendingId: string;
  approved: boolean;
  identity: ChatIdentity;
}

export type ChatGateway = {
  sendMessage: (input: SendMessageInput, signal?: AbortSignal) => Promise<TurnEnvelope>;
  confirmAction: (input: ConfirmActionInput, signal?: AbortSignal) => Promise<TurnEnvelope>;
};
