// NP-183 - Next.js server Sentry
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN || "";

Sentry.init({
  dsn: dsn || undefined,
  enabled: Boolean(dsn),
  environment: process.env.SENTRY_ENVIRONMENT || process.env.NODE_ENV,
  release: process.env.SENTRY_RELEASE || process.env.NEXT_PUBLIC_SENTRY_RELEASE,
  sendDefaultPii: false,
  tracesSampleRate: Number(process.env.SENTRY_TRACES_SAMPLE_RATE || 0.1),
  beforeSend(event) {
    if (event.user) {
      event.user = { id: event.user.id };
    }
    if (event.request?.headers) {
      for (const key of Object.keys(event.request.headers)) {
        if (/authorization|cookie|token|secret/i.test(key)) {
          event.request.headers[key] = "***";
        }
      }
    }
    return event;
  },
});
