import type { ZodType } from "zod";

import { env } from "@/shared/env";

export const API_URL = env.VITE_API_URL ?? "http://localhost:8000";

export class ResponseShapeError extends Error {
  constructor(path: string, detail: string) {
    super(`Unexpected response shape for ${path}: ${detail}`);
    this.name = "ResponseShapeError";
  }
}

// The wire is untrusted until a schema accepts it: a contract change fails here, not three components deeper.
export const getValidated = async <T>(
  path: string,
  schema: ZodType<T>,
  signal?: AbortSignal,
): Promise<T> => {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }

  const parsed = schema.safeParse(await response.json());
  if (!parsed.success) {
    throw new ResponseShapeError(path, parsed.error.message);
  }
  return parsed.data;
};
