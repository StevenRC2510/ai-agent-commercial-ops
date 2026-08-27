import { createContext, useContext } from "react";

import type { ChatGateway } from "./ports.types";

export const ChatGatewayContext = createContext<ChatGateway | null>(null);

export const useChatGateway = (): ChatGateway => {
  const gateway = useContext(ChatGatewayContext);
  if (!gateway) {
    throw new Error("useChatGateway was called outside a ChatGatewayProvider");
  }
  return gateway;
};
