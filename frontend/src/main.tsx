import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/app/App";
import { ErrorBoundary } from "@/app/ErrorBoundary";
import { GatewayProvider } from "@/app/providers/GatewayProvider";
import { QueryProvider } from "@/app/providers/QueryProvider";

import "./index.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found in index.html");
}

createRoot(rootElement).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryProvider>
        <GatewayProvider>
          <App />
        </GatewayProvider>
      </QueryProvider>
    </ErrorBoundary>
  </StrictMode>,
);
