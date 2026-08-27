import { ChatGatewayContext } from "./gatewayContext";
import type { ChatGatewayProviderProps } from "./ChatGatewayProvider.types";

export const ChatGatewayProvider = ({ gateway, children }: ChatGatewayProviderProps) => (
  <ChatGatewayContext.Provider value={gateway}>{children}</ChatGatewayContext.Provider>
);
