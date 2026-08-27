import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { HealthIndicator } from "./HealthIndicator";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("HealthIndicator", () => {
  it("shows a loading state before the request resolves", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {})),
    );
    render(<HealthIndicator />, { wrapper });
    expect(screen.getByRole("status")).toHaveTextContent(/verificando/i);
  });

  it("shows the online state when the backend answers", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
        ),
    );
    render(<HealthIndicator />, { wrapper });
    expect(await screen.findByText(/en línea/i)).toBeInTheDocument();
  });

  it("shows an explicit error state instead of a blank screen", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network down")),
    );
    render(<HealthIndicator />, { wrapper });
    expect(await screen.findByText(/sin conexión/i)).toBeInTheDocument();
  });
});
