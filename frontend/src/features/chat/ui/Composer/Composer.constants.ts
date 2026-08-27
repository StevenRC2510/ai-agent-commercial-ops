export const REGION = "shrink-0 border-t border-line bg-canvas px-4 py-4 sm:px-6";

export const MEASURE = "mx-auto w-full max-w-[70ch]";

export const LOCK_HINT = "mb-2 flex items-center gap-2 text-xs text-attention";

export const LOCK_DOT = "h-1.5 w-1.5 shrink-0 rounded-full bg-attention";

export const FIELD =
  "flex items-end gap-2 rounded-2xl bg-surface-sunken p-2 ring-1 ring-inset ring-line transition duration-200 focus-within:ring-2 focus-within:ring-accent/60 motion-reduce:transition-none";

export const FIELD_LOCKED = "opacity-60";

export const INPUT =
  "max-h-40 min-h-[2.5rem] flex-1 resize-none bg-transparent px-3 py-2.5 text-[0.9375rem] leading-6 text-ink outline-none placeholder:text-ink-subtle disabled:text-ink-subtle";

export const SEND =
  "h-10 w-10 shrink-0 rounded-xl bg-accent text-accent-fg transition duration-200 hover:bg-accent-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas active:scale-95 disabled:bg-surface disabled:text-ink-subtle disabled:ring-1 disabled:ring-inset disabled:ring-line disabled:active:scale-100 motion-reduce:transition-none";

export const KEY_HINT = "mt-2 text-center text-[0.6875rem] text-ink-subtle";

export const KEY_HINT_TEXT = "Enter envía · Shift + Enter salta de línea";

export const INPUT_ID = "chat-composer";

export const LABEL = "Mensaje para el agente";

export const PLACEHOLDER = "Escribe tu mensaje…";

export const SEND_LABEL = "Enviar";

// Mirrors the backend's MAX_MESSAGE_CHARS: refuse here rather than spend a request.
export const MAX_MESSAGE_CHARS = 2000;
