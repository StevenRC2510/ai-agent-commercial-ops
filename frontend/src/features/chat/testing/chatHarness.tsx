import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ChatGatewayProvider } from "../application/ChatGatewayProvider";
import { createFakeChatGateway } from "../infrastructure/FakeChatGateway";
import type { ScriptedTurn } from "../infrastructure/FakeChatGateway.types";

import type { ChatHarness, HarnessWrapperProps } from "./chatHarness.types";

// Re-exported so a ui/ test never has to import an adapter to script one.
export { wireTurn } from "../infrastructure/FakeChatGateway";

export const createChatHarness = (script: readonly ScriptedTurn[]): ChatHarness => {
  const gateway = createFakeChatGateway(script);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  const wrapper = ({ children }: HarnessWrapperProps) => (
    <QueryClientProvider client={client}>
      <ChatGatewayProvider gateway={gateway}>{children}</ChatGatewayProvider>
    </QueryClientProvider>
  );

  return { gateway, wrapper };
};
