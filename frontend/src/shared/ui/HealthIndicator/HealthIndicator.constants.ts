import { z } from "zod";

import type { HealthState } from "./HealthIndicator.types";

export const healthSchema = z.object({ status: z.string() });

export const HEALTH_QUERY_KEY = ["health"] as const;

export const STATE_STYLES: Record<HealthState, string> = {
  loading: "text-amber-600",
  online: "text-green-600",
  offline: "text-red-600",
};

export const STATE_LABELS: Record<HealthState, string> = {
  loading: "Verificando…",
  online: "En línea",
  offline: "Sin conexión",
};
