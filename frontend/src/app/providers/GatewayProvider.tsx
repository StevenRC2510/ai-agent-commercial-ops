import { ChatGatewayProvider, createHttpChatGateway } from "@/features/chat";
import { API_URL } from "@/shared/lib/httpClient";

import type { GatewayProviderProps } from "./GatewayProvider.types";

const gateway = createHttpChatGateway(API_URL);

export const GatewayProvider = ({ children }: GatewayProviderProps) => (
  <ChatGatewayProvider gateway={gateway}>{children}</ChatGatewayProvider>
);
