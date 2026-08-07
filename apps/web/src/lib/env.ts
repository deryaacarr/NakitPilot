/**
 * Central env access for the web app.
 * Public values must use NEXT_PUBLIC_*; never expose secrets to the client bundle.
 */

function requiredPublic(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export const env = {
  appName: requiredPublic("NEXT_PUBLIC_APP_NAME", "NakitPilot"),
  appUrl: requiredPublic("NEXT_PUBLIC_APP_URL", "http://localhost:3000"),
  apiUrl: requiredPublic("NEXT_PUBLIC_API_URL", "http://127.0.0.1:8000"),
  /** Server-only; empty when unset. Do not pass to client components. */
  sentryDsn: process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN ?? "",
} as const;
