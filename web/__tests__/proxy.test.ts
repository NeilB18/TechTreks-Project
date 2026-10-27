import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { config, proxy } from "@/proxy";

describe("proxy", () => {
  it("passes the page's host and scheme, and skips ngrok's warning page", () => {
    const res = proxy(new NextRequest("https://tripbot.vercel.app/accounts/google/login/"));
    expect(res.headers.get("x-middleware-request-x-forwarded-host")).toBe("tripbot.vercel.app");
    expect(res.headers.get("x-middleware-request-x-forwarded-proto")).toBe("https");
    expect(res.headers.get("x-middleware-request-ngrok-skip-browser-warning")).toBe("1");
  });

  it("only runs on the routes proxied to Django", () => {
    expect(config.matcher).toEqual(["/accounts/:path*", "/api/me/:path*"]);
  });
});
