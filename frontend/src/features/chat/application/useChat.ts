import { useMutation } from "@tanstack/react-query";
import { useCallback, useMemo, useRef, useState } from "react";

import {
  EMPTY_CONVERSATION,
  withSystemMessage,
  withTurn,
  withUserMessage,
} from "../domain/conversation";
import { ROLE_LABELS } from "../domain/roles";
import type { Conversation, TurnEnvelope } from "../domain/conversation.types";
import type { UserRole } from "../domain/roles.types";

import { useChatGateway } from "./gatewayContext";
import { useAbortableRequest } from "./useAbortableRequest";
import {
  ACTOR_ID,
  CONFIRM_ACTION_RETRIES,
  DEFAULT_ROLE,
  RETRY_BACKOFF_MS,
  SEND_MESSAGE_RETRIES,
  SYSTEM_MESSAGES,
} from "./useChat.constants";
import type { UseChatResult } from "./useChat.types";

const newSessionId = (): string => `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

const isAbort = (error: unknown): boolean => error instanceof Error && error.name === "AbortError";

export const useChat = (): UseChatResult => {
  const gateway = useChatGateway();
  const [role, setRole] = useState<UserRole>(DEFAULT_ROLE);
  const [conversation, setConversation] = useState<Conversation>(EMPTY_CONVERSATION);
  const sessionId = useRef(newSessionId());
  const { nextSignal, abort } = useAbortableRequest();

  const identity = useMemo(() => ({ actor: ACTOR_ID, role }), [role]);

  const speak = useCallback((envelope: TurnEnvelope) => {
    setConversation((current) => withTurn(current, envelope));
  }, []);

  const report = useCallback((error: unknown, text: string, dropPending = false) => {
    if (isAbort(error)) return;
    setConversation((current) =>
      withSystemMessage(dropPending ? { ...current, pending: null } : current, text),
    );
  }, []);

  const sendTurn = useMutation({
    mutationFn: (message: string) =>
      gateway.sendMessage({ message, sessionId: sessionId.current, identity }, nextSignal()),
    retry: SEND_MESSAGE_RETRIES,
    retryDelay: (attempt: number) => RETRY_BACKOFF_MS * 2 ** attempt,
    onSuccess: speak,
    onError: (error: unknown) => report(error, SYSTEM_MESSAGES.sendFailed),
  });

  const confirmTurn = useMutation({
    mutationFn: (input: { pendingId: string; approved: boolean }) =>
      gateway.confirmAction({ ...input, identity }, nextSignal()),
    retry: CONFIRM_ACTION_RETRIES,
    onSuccess: speak,
    // The consent is spent either way, so the card goes: uncertainty, never a second ask.
    onError: (error: unknown) => report(error, SYSTEM_MESSAGES.confirmUnresolved, true),
  });

  const send = useCallback(
    (text: string) => {
      const message = text.trim();
      // Consent is out of band: while a card is up, nothing new is said.
      if (!message || conversation.pending || sendTurn.isPending) return;
      setConversation((current) => withUserMessage(current, message));
      sendTurn.mutate(message);
    },
    [conversation.pending, sendTurn],
  );

  const resolvePending = useCallback(
    (approved: boolean) => {
      const pending = conversation.pending;
      if (!pending || confirmTurn.isPending) return;
      confirmTurn.mutate({ pendingId: pending.id, approved });
    },
    [conversation.pending, confirmTurn],
  );

  const reset = useCallback(
    (next: Conversation) => {
      abort();
      sessionId.current = newSessionId();
      setConversation(next);
    },
    [abort],
  );

  const changeRole = useCallback(
    (next: UserRole) => {
      setRole(next);
      const notice = SYSTEM_MESSAGES.sessionReset.replace("{role}", ROLE_LABELS[next]);
      reset(withSystemMessage(EMPTY_CONVERSATION, notice));
    },
    [reset],
  );

  const clear = useCallback(() => reset(EMPTY_CONVERSATION), [reset]);

  return {
    messages: conversation.messages,
    pending: conversation.pending,
    role,
    isThinking: sendTurn.isPending,
    isConfirming: confirmTurn.isPending,
    send,
    resolvePending,
    changeRole,
    clear,
  };
};
