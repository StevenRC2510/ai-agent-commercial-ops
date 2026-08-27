import type { Telemetry } from "./telemetry.types";

export const formatTelemetry = (telemetry: Telemetry): string => {
  const seconds = (telemetry.latencyMs / 1000).toFixed(1);
  const tokens = telemetry.inputTokens + telemetry.outputTokens;
  return `${seconds}s · ${tokens} tok`;
};

export const hasMeasurement = (telemetry: Telemetry): boolean =>
  telemetry.latencyMs > 0 || telemetry.inputTokens + telemetry.outputTokens > 0;
