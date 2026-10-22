import type { NextConfig } from "next";

// With a backend configured, sign-in (/accounts/*) and the signed-in API (/api/me/*)
// are proxied to Django, so the session cookie is set on this site's domain.
const backend = process.env.TRIP_API_URL;

const nextConfig: NextConfig = {
  // Django's routes end in "/"; don't let Next strip it and bounce redirects back and forth.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    if (!backend) return [];
    // `:path*` drops a trailing slash, so slash-ending URLs get their own rules (checked first).
    return [
      { source: "/accounts/:path+/", destination: `${backend}/accounts/:path+/` },
      { source: "/accounts/:path*", destination: `${backend}/accounts/:path*` },
      { source: "/api/me/", destination: `${backend}/api/me/` },
      { source: "/api/me/:path+/", destination: `${backend}/api/me/:path+/` },
      { source: "/api/me/:path*", destination: `${backend}/api/me/:path*` },
    ];
  },
};

export default nextConfig;
