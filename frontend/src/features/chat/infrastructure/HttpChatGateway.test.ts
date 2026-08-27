import { describe, expect, it, vi } from "vitest";

import { ResponseShapeError } from "@/shared/lib/httpClient";

import { createHttpChatGateway } from "./HttpChatGateway";

const BASE_URL = "http://backend.test";
const IDENTITY = { actor: "web-demo", role: "supervisor" } as const;
const SEND_INPUT = { message: "hola", sessionId: "session-1", identity: IDENTITY };

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Trace-Id": "trace-1" },
  });

const stubFetch = (response: Response) => {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

describe("HttpChatGateway", () => {
  it("maps a valid wire response onto the domain envelope", async () => {
    stubFetch(
      jsonResponse({
        type: "confirmation_required",
        text: "¿Confirmas el cambio?",
        trace_id: "trace-1",
        pending_id: "pending-9",
        pending_summary: "Orden #3: de en proceso a entregada",
        telemetry: { latency_ms: 1234, input_tokens: 800, output_tokens: 47, iterations: 2 },
      }),
    );

    const envelope = await createHttpChatGateway(BASE_URL).sendMessage(SEND_INPUT);

    expect(envelope).toEqual({
      type: "confirmation_required",
      text: "¿Confirmas el cambio?",
      traceId: "trace-1",
      pendingId: "pending-9",
      pendingSummary: "Orden #3: de en proceso a entregada",
      reasonCode: null,
      telemetry: { latencyMs: 1234, inputTokens: 800, outputTokens: 47, iterations: 2 },
    });
  });

  it("raises ResponseShapeError instead of crashing when the payload breaks the contract", async () => {
    stubFetch(jsonResponse({ type: "message", trace_id: 42 }));

    await expect(createHttpChatGateway(BASE_URL).sendMessage(SEND_INPUT)).rejects.toBeInstanceOf(
      ResponseShapeError,
    );
  });

  it("sends the identity headers and the snake_case body the backend expects", async () => {
    const fetchMock = stubFetch(jsonResponse({ type: "message", text: "ok", trace_id: "trace-1" }));

    await createHttpChatGateway(BASE_URL).confirmAction({
      pendingId: "pending-9",
      approved: true,
      identity: IDENTITY,
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit & { body: string }];
    expect(url).toBe("http://backend.test/confirm");
    expect(init.headers).toMatchObject({ "X-User-Id": "web-demo", "X-User-Role": "supervisor" });
    expect(JSON.parse(init.body)).toEqual({ pending_id: "pending-9", approved: true });
  });

  it("returns the envelope of a 409 so a stale confirmation is explained, not thrown", async () => {
    stubFetch(
      jsonResponse(
        {
          type: "error",
          text: "Esta confirmación ya no es válida.",
          trace_id: "trace-1",
          reason_code: "state_changed_since_consent",
        },
        409,
      ),
    );

    const envelope = await createHttpChatGateway(BASE_URL).confirmAction({
      pendingId: "pending-9",
      approved: true,
      identity: IDENTITY,
    });

    expect(envelope.reasonCode).toBe("state_changed_since_consent");
  });

  it("throws when a failing status carries no envelope at all", async () => {
    stubFetch(jsonResponse({ detail: "No pude identificar tu sesión." }, 401));

    await expect(createHttpChatGateway(BASE_URL).sendMessage(SEND_INPUT)).rejects.toThrow(/401/);
  });
});
