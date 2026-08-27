import { z } from "zod";

import type { HealthState } from "./HealthIndicator.types";

export const healthSchema = z.object({
  status: z.string(),
  demo_mode: z.boolean().optional(),
});

export const HEALTH_QUERY_KEY = ["health"] as const;

export const STATUS = "hidden items-center gap-1.5 text-xs text-ink-subtle sm:inline-flex";

export const DOT = "h-1.5 w-1.5 shrink-0 rounded-full";

// Colour still carries the meaning, but as a dot rather than a shout.
export const DOT_STYLES: Record<HealthState, string> = {
  loading: "bg-attention",
  online: "bg-positive",
  offline: "bg-danger",
};

export const STATE_LABELS: Record<HealthState, string> = {
  loading: "Verificando…",
  online: "En línea",
  offline: "Sin conexión",
};

// The brief asks for real tool calling, so a simulated model must never pass for one.
export const DEMO_BADGE =
  "inline-flex items-center gap-1.5 rounded-full bg-attention-soft px-2.5 py-1 " +
  "text-xs font-medium text-attention ring-1 ring-inset ring-attention-line";

export const DEMO_LABEL = "Modo demostración · modelo simulado";
