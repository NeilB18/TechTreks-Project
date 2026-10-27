import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// With a backend configured, sign-in (/accounts/*) and the signed-in API (/api/me/*) are
// proxied to Django, so the session cookie is set on this site's domain. The path goes
// through exactly as the browser sent it: Django's routes differ by a trailing slash
// (/accounts/google/login/ vs /api/me/link-code), and on Vercel a slash-ending rewrite rule
// in next.config also matched /api/me/link-code and added a slash, so Django returned 404.
//
// Django builds Google's callback URL from the page's own host and scheme, so pass those on.
// When Django sits behind an ngrok tunnel, ngrok answers browser requests with a warning
// page unless the skip header is set.
export function proxy(request: NextRequest) {
  const backend = process.env.TRIP_API_URL;
  if (!backend) return NextResponse.next();
  const headers = new Headers(request.headers);
  headers.set("ngrok-skip-browser-warning", "1");
  headers.set("x-forwarded-host", request.nextUrl.host);
  headers.set("x-forwarded-proto", request.nextUrl.protocol.replace(":", ""));
  const target = new URL(request.nextUrl.pathname + request.nextUrl.search, backend);
  return NextResponse.rewrite(target, { request: { headers } });
}

export const config = {
  matcher: ["/accounts/:path*", "/api/me/:path*"],
};
