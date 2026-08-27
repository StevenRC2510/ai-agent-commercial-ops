export const SCROLLER = "flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain";

// mt-auto pins a short conversation to the bottom, the way a chat reads.
export const MEASURE = "mx-auto flex w-full max-w-[70ch] flex-1 flex-col gap-6 px-4 py-8 sm:px-6";

export const STACK = "mt-auto flex flex-col gap-6";

export const THINKING_ROW = "flex items-center gap-2 text-sm text-ink-subtle";

export const THINKING_DOT = "h-1.5 w-1.5 rounded-full bg-ink-subtle motion-safe:animate-wave";

// Inline styles, not classes: the animation shorthand would reset a class-level delay.
export const THINKING_DELAYS = ["0ms", "160ms", "320ms"];

export const THINKING_LABEL = "Pensando";
