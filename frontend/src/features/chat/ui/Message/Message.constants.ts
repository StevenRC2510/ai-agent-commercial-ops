import type { MessageAuthor } from "../../domain/conversation.types";

export const ROW_STYLES: Record<MessageAuthor, string> = {
  user: "items-end",
  agent: "items-start",
  system: "items-center",
};

// The agent speaks as prose on the canvas, not from inside a chip: it is the content, not a widget.
export const BUBBLE_STYLES: Record<MessageAuthor, string> = {
  user: "max-w-[42ch] rounded-2xl bg-surface-sunken px-4 py-2.5 text-ink ring-1 ring-line/60",
  agent: "w-full text-ink",
  system: "max-w-[52ch] text-center text-xs text-ink-subtle",
};

export const DENIAL_BUBBLE =
  "w-full rounded-2xl border-l-2 border-attention bg-attention-soft px-4 py-3.5 text-ink";

export const DENIAL_EYEBROW =
  "mb-1.5 block text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-attention";

export const DENIAL_LABEL = "Solicitud denegada";

export const AUTHOR_LABELS: Record<MessageAuthor, string> = {
  user: "Tú",
  agent: "Agente",
  system: "Sistema",
};

export const ROW = "flex flex-col motion-safe:animate-enter";

export const BUBBLE = "text-[0.9375rem] leading-7";

export const PLAIN_TEXT = "whitespace-pre-wrap break-words";

export const TABLE_TEXT =
  "overflow-x-auto whitespace-pre-wrap rounded-xl bg-surface-sunken p-3 font-mono text-xs leading-6 tabular-nums";

export const META = "mt-1.5 text-[0.6875rem] tabular-nums text-ink-subtle";
