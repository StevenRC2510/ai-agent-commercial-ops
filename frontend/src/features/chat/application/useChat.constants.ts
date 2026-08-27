import type { UserRole } from "../domain/roles.types";

// This demo authenticates nobody: the actor is fixed and the role is what the user switches.
export const ACTOR_ID = "web-demo";

export const DEFAULT_ROLE: UserRole = "operator";

// ADR 0006: a message is a read from the client's side, a confirmation is consent.
export const SEND_MESSAGE_RETRIES = 2;
export const CONFIRM_ACTION_RETRIES = 0;
export const RETRY_BACKOFF_MS = 300;

export const SYSTEM_MESSAGES = {
  sendFailed: "No pude enviar tu mensaje. Revisa la conexión e inténtalo de nuevo.",
  confirmUnresolved:
    "Se perdió la respuesta de la confirmación. No sé si el cambio llegó a aplicarse: " +
    "revisa el estado de la orden antes de volver a pedirlo.",
  sessionReset: "Sesión reiniciada. Ahora escribes como {role}.",
};
