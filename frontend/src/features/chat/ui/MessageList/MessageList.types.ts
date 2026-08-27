import type { ChatMessage } from "../../domain/conversation.types";

export interface MessageListProps {
  messages: readonly ChatMessage[];
  isThinking: boolean;
  onPickExample: (prompt: string) => void;
}
