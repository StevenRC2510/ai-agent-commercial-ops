import { useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

import { cn } from "@/shared/lib/cn";

import {
  FIELD,
  FIELD_LOCKED,
  INPUT,
  INPUT_ID,
  KEY_HINT,
  KEY_HINT_TEXT,
  LABEL,
  LOCK_DOT,
  LOCK_HINT,
  MAX_MESSAGE_CHARS,
  MEASURE,
  PLACEHOLDER,
  REGION,
  SEND,
  SEND_LABEL,
} from "./Composer.constants";
import type { ComposerProps } from "./Composer.types";

export const Composer = ({ disabled, lockedHint, onSend }: ComposerProps) => {
  const [draft, setDraft] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!disabled) input.current?.focus();
  }, [disabled]);

  const resize = (element: HTMLTextAreaElement) => {
    element.style.height = "auto";
    if (element.scrollHeight) element.style.height = `${element.scrollHeight}px`;
  };

  const send = () => {
    if (disabled || !draft.trim()) return;
    onSend(draft);
    setDraft("");
    if (input.current) input.current.style.height = "auto";
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    send();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    send();
  };

  return (
    <div className={REGION}>
      <div className={MEASURE}>
        {lockedHint && (
          <p className={LOCK_HINT}>
            <span aria-hidden="true" className={LOCK_DOT} />
            {lockedHint}
          </p>
        )}
        <form onSubmit={handleSubmit} className={cn(FIELD, disabled && FIELD_LOCKED)}>
          <label htmlFor={INPUT_ID} className="sr-only">
            {LABEL}
          </label>
          <textarea
            id={INPUT_ID}
            ref={input}
            rows={1}
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              resize(event.target);
            }}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            maxLength={MAX_MESSAGE_CHARS}
            placeholder={PLACEHOLDER}
            className={INPUT}
          />
          <button
            type="submit"
            aria-label={SEND_LABEL}
            disabled={disabled || !draft.trim()}
            className={SEND}
          >
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" className="mx-auto h-4 w-4">
              <path
                d="M10 16V4m0 0L5 9m5-5 5 5"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </form>
        <p className={KEY_HINT}>{KEY_HINT_TEXT}</p>
      </div>
    </div>
  );
};
