import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Sign-in and the signed-in API are rewritten to Django (next.config.ts). When Django sits
// behind an ngrok tunnel, ngrok answers browser requests with a warning page unless this
// header is set, and the trip page's own host must reach Django so it builds the right
// Google callback URL. Setting both here covers hosts that don't forward them.
export function proxy(request: NextRequest) {
  const headers = new Headers(request.headers);
  headers.set("ngrok-skip-browser-warning", "1");
  headers.set("x-forwarded-host", request.nextUrl.host);
  headers.set("x-forwarded-proto", request.nextUrl.protocol.replace(":", ""));
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ["/accounts/:path*", "/api/me/:path*"],
};
