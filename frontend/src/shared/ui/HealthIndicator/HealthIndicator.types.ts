import type { ReactNode } from "react";

export type HealthState = "loading" | "online" | "offline";

export interface WrapperProps {
  children: ReactNode;
}
