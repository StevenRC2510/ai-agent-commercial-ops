import { useChat } from "../../application/useChat";
import { ChatHeader } from "../ChatHeader";
import { Composer } from "../Composer";
import { ConfirmationCard } from "../ConfirmationCard";
import { MessageList } from "../MessageList";

import { LOCKED_HINT, SHELL } from "./ChatWindow.constants";
import type { ChatWindowProps } from "./ChatWindow.types";

export const ChatWindow = ({ brand }: ChatWindowProps) => {
  const chat = useChat();
  const isBusy = chat.isThinking || chat.isConfirming;

  return (
    <div className={SHELL}>
      <ChatHeader
        brand={brand}
        role={chat.role}
        disabled={isBusy}
        onRoleChange={chat.changeRole}
        onClear={chat.clear}
      />
      <MessageList
        messages={chat.messages}
        isThinking={chat.isThinking}
        onPickExample={chat.send}
      />
      {chat.pending && (
        <ConfirmationCard
          summary={chat.pending.summary}
          isConfirming={chat.isConfirming}
          onConfirm={() => chat.resolvePending(true)}
          onCancel={() => chat.resolvePending(false)}
        />
      )}
      <Composer
        disabled={isBusy || chat.pending !== null}
        {...(chat.pending ? { lockedHint: LOCKED_HINT } : {})}
        onSend={chat.send}
      />
    </div>
  );
};
