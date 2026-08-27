import { useEffect, useRef } from "react";

import { cn } from "@/shared/lib/cn";
import { BUTTON_BASE, BUTTON_PRIMARY, BUTTON_QUIET } from "@/shared/ui/buttonStyles";

import {
  ACTIONS,
  CANCEL_LABEL,
  CARD,
  CONFIRM_LABEL,
  EYEBROW,
  EYEBROW_DOT,
  EYEBROW_ROW,
  NOTE,
  NOTE_TEXT,
  REGION,
  SUMMARY,
  TITLE_TEXT,
  TOP_RULE,
} from "./ConfirmationCard.constants";
import type { ConfirmationCardProps } from "./ConfirmationCard.types";

// Consent as an event on an opaque id, never as text the model could have written (ADR 0002).
export const ConfirmationCard = ({
  summary,
  isConfirming,
  onConfirm,
  onCancel,
}: ConfirmationCardProps) => {
  const confirmButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    confirmButton.current?.focus();
  }, []);

  return (
    <div className={REGION}>
      <section role="alert" aria-live="assertive" className={CARD}>
        <span aria-hidden="true" className={TOP_RULE} />
        <div className={EYEBROW_ROW}>
          <span aria-hidden="true" className={EYEBROW_DOT} />
          <h2 className={EYEBROW}>{TITLE_TEXT}</h2>
        </div>
        <p className={SUMMARY}>{summary}</p>
        <p className={NOTE}>{NOTE_TEXT}</p>
        <div className={ACTIONS}>
          <button
            ref={confirmButton}
            type="button"
            onClick={onConfirm}
            disabled={isConfirming}
            className={cn(BUTTON_BASE, BUTTON_PRIMARY)}
          >
            {CONFIRM_LABEL}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={isConfirming}
            className={cn(BUTTON_BASE, BUTTON_QUIET)}
          >
            {CANCEL_LABEL}
          </button>
        </div>
      </section>
    </div>
  );
};
