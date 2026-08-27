// The third one reaches a write, which is the whole point of the demo: it opens the card.
export const EXAMPLE_PROMPTS = [
  "¿Qué órdenes están en proceso?",
  "¿Cuál es el saldo del cliente Autos del Valle?",
  "Cambia la orden #11 a entregada",
];

export const WRAPPER = "m-auto flex w-full max-w-lg flex-col items-center gap-6 py-10 text-center";

export const TITLE = "mb-2 text-xl font-semibold tracking-[-0.02em] text-ink";

export const TITLE_TEXT = "¿Qué necesitas revisar?";

export const LEAD = "max-w-md text-pretty text-sm leading-relaxed text-ink-muted";

export const LEAD_TEXT =
  "Pregunta por órdenes, inventario y clientes. Cambiar el estado de una orden requiere rol de supervisor y tu confirmación explícita.";

export const EXAMPLES = "flex w-full flex-col gap-2";

export const EXAMPLE =
  "group flex w-full items-center justify-between gap-3 rounded-xl bg-surface px-4 py-3 text-left text-sm text-ink-muted ring-1 ring-inset ring-line transition duration-200 hover:bg-surface-sunken hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent motion-reduce:transition-none";

export const EXAMPLE_ARROW =
  "h-4 w-4 shrink-0 text-ink-subtle transition-transform duration-200 group-hover:translate-x-0.5 motion-reduce:transition-none";
