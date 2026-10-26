import { describe, expect, it, vi } from "vitest";

import { buildStorageState, TOKEN_KEY, tokenFromLink } from "./session";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("agent-testnutzer session", () => {
  it("baut storageState aus Magic-Link und Tausch", async () => {
    const fetchImpl = vi.fn(async (url: string | URL | Request, _init?: RequestInit) => {
      if (String(url).endsWith("/api/auth/magic-link")) {
        return jsonResponse({ sent: false, dev_link: "http://localhost:3100/login/exchange?token=abc" });
      }
      return jsonResponse({ token: "jwt-wert" });
    });
    const state = await buildStorageState({
      apiUrl: "http://api.test/",
      baseUrl: "http://localhost:3100/werk",
      email: "agent@example.com",
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });
    expect(state).toEqual({
      cookies: [],
      origins: [{ origin: "http://localhost:3100", localStorage: [{ name: TOKEN_KEY, value: "jwt-wert" }] }],
    });
    expect(fetchImpl.mock.calls.map(([url]) => String(url))).toEqual([
      "http://api.test/api/auth/magic-link",
      "http://api.test/api/auth/exchange",
    ]);
    expect(JSON.parse(String(fetchImpl.mock.calls[1][1]?.body))).toEqual({ token: "abc" });
  });

  it("bricht ohne dev_link ab", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ sent: true, dev_link: null }));
    await expect(
      buildStorageState({ apiUrl: "http://api.test", baseUrl: "http://x", email: "a@b.de", fetchImpl: fetchImpl as unknown as typeof fetch }),
    ).rejects.toThrow(/AUTH_DEV_LINK/);
  });

  it("meldet HTTP-Fehler und Links ohne token", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse({ detail: "nein" }, 502));
    await expect(
      buildStorageState({ apiUrl: "http://api.test", baseUrl: "http://x", email: "a@b.de", fetchImpl: fetchImpl as unknown as typeof fetch }),
    ).rejects.toThrow(/HTTP 502/);
    expect(() => tokenFromLink("http://x/login/exchange")).toThrow();
  });
});
