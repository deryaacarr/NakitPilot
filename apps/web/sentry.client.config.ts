// NP-183 - browser Sentry (scrub PII; IDs only)
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN || process.env.SENTRY_DSN || "";

const SENSITIVE = /password|token|authorization|cookie|secret|refresh|access|email|phone|tax/i;

function scrubValue(key: string | undefined, value: unknown): unknown {
  if (key && SENSITIVE.test(key)) return "***";
  if (typeof value === "string") {
    return value
      .replace(/\bBearer\s+[A-Za-z0-9._\-+=/]+/gi, "Bearer ***")
      .replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g, "***@***");
  }
  return value;
}

function beforeSend(event: Sentry.ErrorEvent): Sentry.ErrorEvent | null {
  if (event.request?.headers) {
    for (const key of Object.keys(event.request.headers)) {
      if (SENSITIVE.test(key)) {
        event.request.headers[key] = "***";
      }
    }
  }
  if (event.user) {
    event.user = { id: event.user.id };
  }
  if (event.extra) {
    for (const [key, value] of Object.entries(event.extra)) {
      event.extra[key] = scrubValue(key, value);
    }
  }
  return event;
}

Sentry.init({
  dsn: dsn || undefined,
  enabled: Boolean(dsn),
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV,
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE || process.env.SENTRY_RELEASE,
  sendDefaultPii: false,
  beforeSend,
  tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE || 0.1),
});
