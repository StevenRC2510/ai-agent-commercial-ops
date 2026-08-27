import { describe, expect, it } from "vitest";

import { formatTelemetry, hasMeasurement } from "./telemetry";

const reading = { latencyMs: 1234, inputTokens: 800, outputTokens: 47, iterations: 2 };

describe("telemetry", () => {
  it("reads as seconds and total tokens", () => {
    expect(formatTelemetry(reading)).toBe("1.2s · 847 tok");
  });

  it("is a measurement when something was actually spent", () => {
    expect(hasMeasurement(reading)).toBe(true);
  });

  // DEMO_MODE bills nothing, and "0.0s · 0 tok" reads as a broken meter rather than an honest zero.
  it("is not a measurement when nothing was measured", () => {
    expect(hasMeasurement({ latencyMs: 0, inputTokens: 0, outputTokens: 0, iterations: 2 })).toBe(
      false,
    );
  });
});
