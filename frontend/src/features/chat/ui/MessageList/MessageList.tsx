import { useEffect, useRef } from "react";

import { EmptyState } from "../EmptyState";
import { Message } from "../Message";

import {
  MEASURE,
  SCROLLER,
  STACK,
  THINKING_DELAYS,
  THINKING_DOT,
  THINKING_LABEL,
  THINKING_ROW,
} from "./MessageList.constants";
import type { MessageListProps } from "./MessageList.types";

export const MessageList = ({ messages, isThinking, onPickExample }: MessageListProps) => {
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages, isThinking]);

  return (
    <div role="log" aria-live="polite" aria-relevant="additions" className={SCROLLER}>
      <div className={MEASURE}>
        {messages.length === 0 && !isThinking ? (
          <EmptyState onPick={onPickExample} />
        ) : (
          <div className={STACK}>
            {messages.map((message) => (
              <Message key={message.id} message={message} />
            ))}
            {isThinking && (
              <p role="status" className={THINKING_ROW}>
                {THINKING_LABEL}
                <span aria-hidden="true" className="flex gap-1">
                  {THINKING_DELAYS.map((delay) => (
                    <span key={delay} className={THINKING_DOT} style={{ animationDelay: delay }} />
                  ))}
                </span>
              </p>
            )}
          </div>
        )}
        <div ref={end} />
      </div>
    </div>
  );
};
