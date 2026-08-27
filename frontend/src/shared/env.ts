import { envSchema } from "./env.schema";
import type { Env } from "./env.types";

// Mirrors app/infrastructure/env_check.py: fail at startup, not three components deep.
export const parseEnv = (source: unknown): Env => {
  const result = envSchema.safeParse(source);
  if (!result.success) {
    throw new Error(`Invalid frontend environment: ${result.error.message}`);
  }
  return result.data;
};

export const env = parseEnv(import.meta.env);
