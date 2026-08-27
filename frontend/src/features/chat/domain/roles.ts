import type { UserRole } from "./roles.types";

export const USER_ROLES: readonly UserRole[] = ["operator", "supervisor"];

/** The role names are part of the ubiquitous language, and it is Spanish. */
export const ROLE_LABELS: Record<UserRole, string> = {
  operator: "Operador",
  supervisor: "Supervisor",
};
