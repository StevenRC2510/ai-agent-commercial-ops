import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import type { ReactNode } from "react";

// Read retries are safe. Mutation retry policy is decided per mutation —
// see docs/adr/0006-no-retry-on-confirmation.md.
const client = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, staleTime: 30_000 },
    mutations: { retry: 0 },
  },
});

export function QueryProvider({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      {children}
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
