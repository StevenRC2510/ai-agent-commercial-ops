import { ChatWindow } from "@/features/chat";
import { HealthIndicator } from "@/shared/ui/HealthIndicator";

import { BRAND, MARK, NAME, SEPARATOR, SHELL } from "./App.constants";

const Brand = () => (
  <div className={BRAND}>
    <span aria-hidden="true" className={MARK} />
    <span className={NAME}>Operaciones Comerciales</span>
    <span aria-hidden="true" className={SEPARATOR} />
    <HealthIndicator />
  </div>
);

export const App = () => (
  <div className={SHELL}>
    <ChatWindow brand={<Brand />} />
  </div>
);
