import { cn } from "@/shared/lib/cn";

import { formatTelemetry, hasMeasurement } from "../../domain/telemetry";

import {
  AUTHOR_LABELS,
  BUBBLE,
  BUBBLE_STYLES,
  DENIAL_BUBBLE,
  DENIAL_EYEBROW,
  DENIAL_LABEL,
  META,
  PLAIN_TEXT,
  ROW,
  ROW_STYLES,
  TABLE_TEXT,
} from "./Message.constants";
import type { MessageProps } from "./Message.types";

const looksTabular = (text: string): boolean => /^\s*\|/m.test(text);

// Rendered as text, never HTML: the seeded data carries a prompt-injection payload on purpose (SPEC-2 §9.3).
export const Message = ({ message }: MessageProps) => {
  const { author, text, tone, traceId, telemetry } = message;
  const isDenial = tone === "denial";
  const measured = telemetry && hasMeasurement(telemetry);

  return (
    <div className={cn(ROW, ROW_STYLES[author])}>
      <article
        aria-label={AUTHOR_LABELS[author]}
        className={cn(BUBBLE, isDenial ? DENIAL_BUBBLE : BUBBLE_STYLES[author])}
      >
        {isDenial && <span className={DENIAL_EYEBROW}>{DENIAL_LABEL}</span>}
        <p className={looksTabular(text) ? TABLE_TEXT : PLAIN_TEXT}>{text}</p>
      </article>
      {traceId && (
        <p className={META}>
          {traceId}
          {measured ? ` · ${formatTelemetry(telemetry)}` : ""}
        </p>
      )}
    </div>
  );
};
