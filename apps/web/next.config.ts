import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  // Playwright / local tooling often hits 127.0.0.1 while `next dev` binds to localhost.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // NP-180 — lean production image via Next standalone output.
  output: "standalone",
};

export default withSentryConfig(nextConfig, {
  silent: true,
  // Disable source map upload unless SENTRY_AUTH_TOKEN is set in CI.
  sourcemaps: { disable: !process.env.SENTRY_AUTH_TOKEN },
});
