import type { ZodType } from "zod";

import { env } from "@/shared/env";

const API_URL = env.VITE_API_URL ?? "http://localhost:8000";

/** The backend answered, but not in the shape the contract promises. */
export class ResponseShapeError extends Error {
  constructor(path: string, detail: string) {
    super(`Unexpected response shape for ${path}: ${detail}`);
    this.name = "ResponseShapeError";
  }
}

/**
 * Fetch and validate. What arrives over the network is untrusted data until
 * a schema accepts it, so a contract change fails here with a clear message
 * rather than as an undefined three components deeper.
 */
export async function getValidated<T>(
  path: string,
  schema: ZodType<T>,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }

  const parsed = schema.safeParse(await response.json());
  if (!parsed.success) {
    throw new ResponseShapeError(path, parsed.error.message);
  }
  return parsed.data;
}
