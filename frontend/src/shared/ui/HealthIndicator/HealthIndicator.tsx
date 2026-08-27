import { useQuery } from "@tanstack/react-query";

import { cn } from "@/shared/lib/cn";
import { getValidated } from "@/shared/lib/httpClient";

import {
  DEMO_BADGE,
  DEMO_LABEL,
  DOT,
  DOT_STYLES,
  HEALTH_QUERY_KEY,
  STATE_LABELS,
  STATUS,
  healthSchema,
} from "./HealthIndicator.constants";
import type { HealthState } from "./HealthIndicator.types";

const resolveState = (
  isPending: boolean,
  isError: boolean,
  status: string | undefined,
): HealthState => {
  if (isPending) return "loading";
  if (isError || status !== "ok") return "offline";
  return "online";
};

export const HealthIndicator = () => {
  const { data, isPending, isError } = useQuery({
    queryKey: HEALTH_QUERY_KEY,
    queryFn: ({ signal }) => getValidated("/health", healthSchema, signal),
  });

  const state = resolveState(isPending, isError, data?.status);

  return (
    <>
      <p role="status" aria-live="polite" className={STATUS}>
        <span aria-hidden="true" className={cn(DOT, DOT_STYLES[state])} />
        {STATE_LABELS[state]}
      </p>
      {data?.demo_mode ? <span className={DEMO_BADGE}>{DEMO_LABEL}</span> : null}
    </>
  );
};
