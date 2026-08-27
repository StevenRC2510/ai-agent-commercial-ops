import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { WrapperProps } from "./HealthIndicator.types";
import { describe, expect, it, vi } from "vitest";

import { HealthIndicator } from "./HealthIndicator";

const stubHealth = (body: Record<string, unknown>) =>
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 })),
  );

const wrapper = ({ children }: WrapperProps) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
};

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
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 })),
    );
    render(<HealthIndicator />, { wrapper });
    expect(await screen.findByText(/en línea/i)).toBeInTheDocument();
  });

  it("shows an explicit error state instead of a blank screen", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    render(<HealthIndicator />, { wrapper });
    expect(await screen.findByText(/sin conexión/i)).toBeInTheDocument();
  });

  it("says the model is simulated so a demo answer never passes for a real one", async () => {
    stubHealth({ status: "ok", demo_mode: true });
    render(<HealthIndicator />, { wrapper });
    expect(await screen.findByText(/modo demostración/i)).toBeInTheDocument();
  });

  it("stays quiet when a real model is answering", async () => {
    stubHealth({ status: "ok", demo_mode: false });
    render(<HealthIndicator />, { wrapper });
    await screen.findByText(/en línea/i);
    expect(screen.queryByText(/modo demostración/i)).not.toBeInTheDocument();
  });
});
