import type { ReactNode } from "react";

import type { FakeChatGateway } from "../infrastructure/FakeChatGateway.types";

export interface HarnessWrapperProps {
  children: ReactNode;
}

export interface ChatHarness {
  gateway: FakeChatGateway;
  wrapper: (props: HarnessWrapperProps) => ReactNode;
}
