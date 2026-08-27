import type { ChatMessage, PendingAction } from "../domain/conversation.types";
import type { UserRole } from "../domain/roles.types";

export interface UseChatResult {
  messages: readonly ChatMessage[];
  pending: PendingAction | null;
  role: UserRole;
  isThinking: boolean;
  isConfirming: boolean;
  send: (text: string) => void;
  resolvePending: (approved: boolean) => void;
  changeRole: (role: UserRole) => void;
  clear: () => void;
}
