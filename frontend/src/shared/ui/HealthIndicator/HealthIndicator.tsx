import { useQuery } from "@tanstack/react-query";

import { cn } from "@/shared/lib/cn";
import { getValidated } from "@/shared/lib/httpClient";

import {
  HEALTH_QUERY_KEY,
  STATE_LABELS,
  STATE_STYLES,
  healthSchema,
} from "./HealthIndicator.constants";
import type { HealthState } from "./HealthIndicator.types";

function resolveState(
  isPending: boolean,
  isError: boolean,
  status: string | undefined,
): HealthState {
  if (isPending) return "loading";
  if (isError || status !== "ok") return "offline";
  return "online";
}

export function HealthIndicator() {
  const { data, isPending, isError } = useQuery({
    queryKey: HEALTH_QUERY_KEY,
    queryFn: ({ signal }) => getValidated("/health", healthSchema, signal),
  });

  const state = resolveState(isPending, isError, data?.status);

  return (
    <p
      role="status"
      aria-live="polite"
      className={cn("text-sm font-medium", STATE_STYLES[state])}
    >
      Backend: {STATE_LABELS[state]}
    </p>
  );
}
