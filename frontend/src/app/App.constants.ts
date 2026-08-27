export const SHELL = "flex h-[100dvh] flex-col overflow-hidden bg-canvas text-ink";

export const BRAND = "flex min-w-0 items-center gap-2.5";

export const MARK = "h-6 w-6 shrink-0 rounded-lg bg-accent";

// Below sm the mark alone carries the brand: a name clipped to "Op…" reads as breakage.
export const NAME =
  "hidden truncate text-[0.9375rem] font-semibold tracking-[-0.02em] text-ink sm:block";

export const SEPARATOR = "hidden h-4 w-px bg-line sm:block";
