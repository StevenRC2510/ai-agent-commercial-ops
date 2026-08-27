import { z } from "zod";

import type { HealthState } from "./HealthIndicator.types";

export const healthSchema = z.object({ status: z.string() });

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
