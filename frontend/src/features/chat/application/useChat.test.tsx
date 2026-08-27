import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { wireTurn } from "../infrastructure/FakeChatGateway";
import { createChatHarness } from "../testing/chatHarness";

import { useChat } from "./useChat";

const PENDING_TURN = wireTurn({
  type: "confirmation_required",
  text: "Necesito tu confirmación.",
  pending_id: "pending-9",
  pending_summary: "Orden #3: de en proceso a entregada",
});

const RETRY_TIMEOUT = { timeout: 4000 };

describe("useChat", () => {
  it("blocks the conversation while a confirmation is pending", async () => {
    const { gateway, wrapper } = createChatHarness([PENDING_TURN]);
    const { result } = renderHook(() => useChat(), { wrapper });

    act(() => result.current.send("cambia la orden #3 a entregada"));
    await waitFor(() => expect(result.current.pending).not.toBeNull());

    act(() => result.current.send("otra cosa"));

    expect(gateway.sendCalls).toHaveLength(1);
    expect(result.current.pending?.summary).toBe("Orden #3: de en proceso a entregada");
  });

  it("reopens the conversation once the pending action resolves", async () => {
    const { gateway, wrapper } = createChatHarness([
      PENDING_TURN,
      wireTurn({ text: "Cambio aplicado." }),
      wireTurn({ text: "Listo." }),
    ]);
    const { result } = renderHook(() => useChat(), { wrapper });

    act(() => result.current.send("cambia la orden #3 a entregada"));
    await waitFor(() => expect(result.current.pending).not.toBeNull());

    act(() => result.current.resolvePending(true));
    await waitFor(() => expect(result.current.pending).toBeNull());

    expect(gateway.confirmCalls).toHaveLength(1);
    expect(gateway.confirmCalls[0]).toMatchObject({ pendingId: "pending-9", approved: true });

    act(() => result.current.send("gracias"));
    await waitFor(() => expect(gateway.sendCalls).toHaveLength(2));
  });

  it("never retries a failed confirmation — ADR 0006", async () => {
    const { gateway, wrapper } = createChatHarness([
      PENDING_TURN,
      new Error("network down"),
      new Error("network down"),
      new Error("network down"),
    ]);
    const { result } = renderHook(() => useChat(), { wrapper });

    act(() => result.current.send("cambia la orden #3 a entregada"));
    await waitFor(() => expect(result.current.pending).not.toBeNull());

    act(() => result.current.resolvePending(true));
    await waitFor(() => expect(result.current.isConfirming).toBe(false), RETRY_TIMEOUT);

    expect(gateway.confirmCalls).toHaveLength(1);
    expect(result.current.messages.at(-1)?.author).toBe("system");
  });

  it("retries a failed message twice — three attempts in total", async () => {
    const { gateway, wrapper } = createChatHarness([
      new Error("network down"),
      new Error("network down"),
      new Error("network down"),
    ]);
    const { result } = renderHook(() => useChat(), { wrapper });

    act(() => result.current.send("hola"));

    await waitFor(() => expect(gateway.sendCalls).toHaveLength(3), RETRY_TIMEOUT);
    await waitFor(() => expect(result.current.messages.at(-1)?.author).toBe("system"));
  });

  it("resets the session and says so when the role changes", async () => {
    const { gateway, wrapper } = createChatHarness([wireTurn({ text: "Listo." })]);
    const { result } = renderHook(() => useChat(), { wrapper });

    act(() => result.current.send("hola"));
    await waitFor(() => expect(result.current.messages).toHaveLength(2));
    expect(gateway.sendCalls[0]?.identity.role).toBe("operator");

    act(() => result.current.changeRole("supervisor"));

    expect(result.current.role).toBe("supervisor");
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]?.author).toBe("system");
    expect(result.current.messages[0]?.text).toMatch(/supervisor/i);
    // The header carries no standing hint, so this notice is the only word the user gets.
    expect(result.current.messages[0]?.text).toMatch(/reiniciada/i);
  });
});
