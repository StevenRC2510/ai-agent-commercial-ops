// Validates the frontend environment before the app starts, the same way
// backend/app/infrastructure/env_check.py validates the backend's.
// Duplicates (not imports) the one-field schema in src/shared/env.ts: that
// module runs in the browser against import.meta.env, this script runs in
// Node against the same variables as resolved by Vite's own .env loader —
// two different runtimes, so keep both in sync by hand if VITE_API_URL's
// contract ever changes.
import { loadEnv } from "vite";
import { z } from "zod";

const envSchema = z.object({
  VITE_API_URL: z.string().url().optional(),
});

const mode = process.env.NODE_ENV ?? "development";
const env = loadEnv(mode, process.cwd());

const result = envSchema.safeParse(env);
if (!result.success) {
  console.error("Frontend environment validation failed:");
  for (const issue of result.error.issues) {
    console.error(`  - ${issue.path.join(".")}: ${issue.message}`);
  }
  process.exit(1);
}

console.log(
  "Environment OK — all required frontend variables are present and valid.",
);
