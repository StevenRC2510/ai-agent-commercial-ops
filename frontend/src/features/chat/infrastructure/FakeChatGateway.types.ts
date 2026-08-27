import type { ChatGateway, ConfirmActionInput, SendMessageInput } from "../application/ports.types";

export type WireTurn = Record<string, unknown>;

export type ScriptedTurn = WireTurn | Error;

export type FakeChatGateway = ChatGateway & {
  sendCalls: SendMessageInput[];
  confirmCalls: ConfirmActionInput[];
};
