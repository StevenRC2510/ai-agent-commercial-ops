import { z } from "zod";

import type { TurnEnvelope } from "../domain/conversation.types";

const telemetrySchema = z.object({
  latency_ms: z.number(),
  input_tokens: z.number(),
  output_tokens: z.number(),
  iterations: z.number(),
});

// Both gateways parse through this, so no test can pass against a shape the backend never produces (ADR 0007).
export const turnResponseSchema = z
  .object({
    type: z.enum(["message", "confirmation_required", "error"]),
    text: z.string(),
    trace_id: z.string(),
    pending_id: z.string().nullish(),
    pending_summary: z.string().nullish(),
    reason_code: z.string().nullish(),
    telemetry: telemetrySchema.nullish(),
  })
  .transform(
    (wire): TurnEnvelope => ({
      type: wire.type,
      text: wire.text,
      traceId: wire.trace_id,
      pendingId: wire.pending_id ?? null,
      pendingSummary: wire.pending_summary ?? null,
      reasonCode: wire.reason_code ?? null,
      telemetry: wire.telemetry
        ? {
            latencyMs: wire.telemetry.latency_ms,
            inputTokens: wire.telemetry.input_tokens,
            outputTokens: wire.telemetry.output_tokens,
            iterations: wire.telemetry.iterations,
          }
        : null,
    }),
  );
