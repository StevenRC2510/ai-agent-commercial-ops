export const CONTROL_BASE =
  "inline-flex items-center justify-center gap-2 rounded-xl text-sm font-medium transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:cursor-not-allowed motion-reduce:transition-none";

export const BUTTON_BASE = CONTROL_BASE;

// A disabled primary goes neutral rather than translucent: a faded accent reads as broken.
export const BUTTON_PRIMARY =
  "h-10 bg-accent px-5 text-accent-fg hover:bg-accent-hover active:scale-[0.98] disabled:bg-surface-sunken disabled:text-ink-subtle disabled:active:scale-100";

export const BUTTON_QUIET =
  "h-10 px-4 text-ink-muted hover:bg-surface-sunken hover:text-ink disabled:text-ink-subtle disabled:hover:bg-transparent";

export const BUTTON_GHOST =
  "h-9 bg-surface px-3 text-ink-muted ring-1 ring-inset ring-line hover:bg-surface-sunken hover:text-ink disabled:text-ink-subtle";
