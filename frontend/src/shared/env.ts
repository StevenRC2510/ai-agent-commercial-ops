import { z } from "zod";

// Mirrors app/infrastructure/env_check.py: fail fast and explicitly at startup,
// not later with an obscure runtime error three components deep.
const envSchema = z.object({
  VITE_API_URL: z.string().url().optional(),
});

export type Env = z.infer<typeof envSchema>;

export function parseEnv(source: unknown): Env {
  const result = envSchema.safeParse(source);
  if (!result.success) {
    throw new Error(`Invalid frontend environment: ${result.error.message}`);
  }
  return result.data;
}

export const env = parseEnv(import.meta.env);
