import type { ReactNode } from "react";

import type { ChatGateway } from "./ports.types";

export interface ChatGatewayProviderProps {
  gateway: ChatGateway;
  children: ReactNode;
}
