import { ResponseShapeError } from "@/shared/lib/httpClient";

import type {
  ChatGateway,
  ChatIdentity,
  ConfirmActionInput,
  SendMessageInput,
} from "../application/ports.types";
import type { TurnEnvelope } from "../domain/conversation.types";

import {
  CHAT_PATH,
  CONFIRM_PATH,
  JSON_HEADERS,
  ROLE_HEADER,
  USER_HEADER,
} from "./HttpChatGateway.constants";
import { turnResponseSchema } from "./turnResponseSchema";

const readBody = async (response: Response): Promise<unknown> => {
  try {
    return (await response.json()) as unknown;
  } catch {
    // A body that is not JSON is not an envelope; the status check below reports it.
    return null;
  }
};

export const createHttpChatGateway = (baseUrl: string): ChatGateway => {
  const post = async (
    path: string,
    body: Record<string, unknown>,
    identity: ChatIdentity,
    signal?: AbortSignal,
  ): Promise<TurnEnvelope> => {
    const response = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: { ...JSON_HEADERS, [USER_HEADER]: identity.actor, [ROLE_HEADER]: identity.role },
      body: JSON.stringify(body),
      signal,
    });

    // Any status may carry the envelope: 409 a spent consent, 500 the server's fallback.
    const parsed = turnResponseSchema.safeParse(await readBody(response));
    if (parsed.success) return parsed.data;
    if (!response.ok) {
      throw new Error(`Request to ${path} failed with status ${response.status}`);
    }
    throw new ResponseShapeError(path, parsed.error.message);
  };

  return {
    sendMessage: (input: SendMessageInput, signal?: AbortSignal) =>
      post(
        CHAT_PATH,
        { message: input.message, session_id: input.sessionId },
        input.identity,
        signal,
      ),
    confirmAction: (input: ConfirmActionInput, signal?: AbortSignal) =>
      post(
        CONFIRM_PATH,
        { pending_id: input.pendingId, approved: input.approved },
        input.identity,
        signal,
      ),
  };
};
