import { describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { ResponseShapeError, getValidated } from "./httpClient";

const schema = z.object({ status: z.string() });

describe("getValidated", () => {
  it("returns the parsed payload when the response matches the schema", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 })),
    );
    await expect(getValidated("/health", schema)).resolves.toEqual({
      status: "ok",
    });
  });

  it("throws a domain error when the payload does not match the schema", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(new Response(JSON.stringify({ unexpected: true }), { status: 200 })),
    );
    await expect(getValidated("/health", schema)).rejects.toBeInstanceOf(ResponseShapeError);
  });

  it("throws when the response status is not ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 503 })));
    await expect(getValidated("/health", schema)).rejects.toThrow();
  });
});
