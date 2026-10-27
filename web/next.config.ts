import type { NextConfig } from "next";

// Sign-in (/accounts/*) and the signed-in API (/api/me/*) are proxied to Django in
// proxy.ts, which keeps each path exactly as sent.
const nextConfig: NextConfig = {
  // Django's routes end in "/"; don't let Next strip it and bounce redirects back and forth.
  skipTrailingSlashRedirect: true,
};

export default nextConfig;
