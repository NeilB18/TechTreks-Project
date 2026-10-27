import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { config, proxy } from "@/proxy";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("proxy", () => {
  it("forwards the exact path to Django, with or without a trailing slash", () => {
    vi.stubEnv("TRIP_API_URL", "https://backend.example");
    const rewrite = (path: string) =>
      proxy(new NextRequest(`https://tripbot.vercel.app${path}`)).headers.get("x-middleware-rewrite");
    expect(rewrite("/api/me/link-code")).toBe("https://backend.example/api/me/link-code");
    expect(rewrite("/api/me/trips/miami/budget")).toBe("https://backend.example/api/me/trips/miami/budget");
    expect(rewrite("/accounts/google/login/?next=/trips/miami"))
      .toBe("https://backend.example/accounts/google/login/?next=/trips/miami");
  });

  it("passes the page's host and scheme, and skips ngrok's warning page", () => {
    vi.stubEnv("TRIP_API_URL", "https://backend.example");
    const res = proxy(new NextRequest("https://tripbot.vercel.app/accounts/google/login/"));
    expect(res.headers.get("x-middleware-request-x-forwarded-host")).toBe("tripbot.vercel.app");
    expect(res.headers.get("x-middleware-request-x-forwarded-proto")).toBe("https");
    expect(res.headers.get("x-middleware-request-ngrok-skip-browser-warning")).toBe("1");
  });

  it("does nothing without a backend", () => {
    vi.stubEnv("TRIP_API_URL", "");
    expect(proxy(new NextRequest("https://x.example/api/me/")).headers.get("x-middleware-rewrite")).toBeNull();
  });

  it("only runs on the routes proxied to Django", () => {
    expect(config.matcher).toEqual(["/accounts/:path*", "/api/me/:path*"]);
  });
});
