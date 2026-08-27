import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createChatHarness, wireTurn } from "../../testing/chatHarness";
import { EXAMPLE_PROMPTS } from "../EmptyState/EmptyState.constants";

import { ChatWindow } from "./ChatWindow";

const PENDING_TURN = wireTurn({
  type: "confirmation_required",
  text: "Necesito tu confirmación.",
  pending_id: "pending-9",
  pending_summary: "Orden #3: de en proceso a entregada",
});

const ask = (text: string) => {
  fireEvent.change(screen.getByLabelText(/mensaje/i), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: /enviar/i }));
};

describe("ChatWindow", () => {
  it("shows an operator's refused write as a denial, never as a card", async () => {
    const { wrapper } = createChatHarness([
      wireTurn({
        type: "error",
        text: "Tu rol no permite cambiar el estado de una orden.",
        reason_code: "write_requires_supervisor",
      }),
    ]);
    render(<ChatWindow brand={<span>Marca</span>} />, { wrapper });

    ask("cambia la orden #3 a entregada");

    expect(await screen.findByText(/tu rol no permite/i)).toBeInTheDocument();
    expect(screen.getByText(/denegada/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("disables the composer while a confirmation card is active", async () => {
    const { wrapper } = createChatHarness([PENDING_TURN]);
    render(<ChatWindow brand={<span>Marca</span>} />, { wrapper });

    ask("cambia la orden #3 a entregada");

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByLabelText(/mensaje/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /enviar/i })).toBeDisabled();
    expect(screen.getByText(/bloqueado/i)).toBeInTheDocument();
  });

  it("executes the change when the supervisor presses Confirmar", async () => {
    const { gateway, wrapper } = createChatHarness([
      PENDING_TURN,
      wireTurn({ text: "Cambio aplicado. Orden #3: de en proceso a entregada" }),
    ]);
    render(<ChatWindow brand={<span>Marca</span>} />, { wrapper });

    ask("cambia la orden #3 a entregada");
    fireEvent.click(await screen.findByRole("button", { name: /confirmar/i }));

    expect(await screen.findByText(/cambio aplicado/i)).toBeInTheDocument();
    expect(gateway.confirmCalls[0]).toMatchObject({ pendingId: "pending-9", approved: true });
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });

  it("changes nothing when the supervisor presses Cancelar", async () => {
    const { gateway, wrapper } = createChatHarness([
      PENDING_TURN,
      wireTurn({ text: "Cancelado. No se aplicó ningún cambio." }),
    ]);
    render(<ChatWindow brand={<span>Marca</span>} />, { wrapper });

    ask("cambia la orden #3 a entregada");
    fireEvent.click(await screen.findByRole("button", { name: /cancelar/i }));

    expect(await screen.findByText(/cancelado/i)).toBeInTheDocument();
    expect(gateway.confirmCalls[0]).toMatchObject({ approved: false });
    expect(screen.getByLabelText(/mensaje/i)).not.toBeDisabled();
  });

  it("sends an example prompt when the user picks one from the empty state", async () => {
    const { gateway, wrapper } = createChatHarness([
      wireTurn({ text: "Hay 4 órdenes en proceso." }),
    ]);
    render(<ChatWindow brand={<span>Marca</span>} />, { wrapper });

    const [first] = EXAMPLE_PROMPTS;
    fireEvent.click(screen.getByRole("button", { name: first }));

    expect(await screen.findByText(/4 órdenes/i)).toBeInTheDocument();
    expect(gateway.sendCalls[0]?.message).toBe(first);
  });

  it("clears the conversation on demand", async () => {
    const { wrapper } = createChatHarness([wireTurn({ text: "Hay 4 órdenes en proceso." })]);
    render(<ChatWindow brand={<span>Marca</span>} />, { wrapper });

    ask("¿cuántas órdenes hay en proceso?");
    expect(await screen.findByText(/4 órdenes/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /limpiar/i }));

    expect(screen.queryByText(/4 órdenes/i)).not.toBeInTheDocument();
  });
});
