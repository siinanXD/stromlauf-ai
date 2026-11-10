import { afterEach, describe, expect, it, vi } from "vitest";

import { api, errorDetail, signalPath } from "./api";

function respond(status: number, body: unknown, statusText = "Error") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status, statusText, headers: { "Content-Type": "application/json" } })),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("errorDetail", () => {
  const response = { status: 404, statusText: "Not Found" };

  it("uses detail.message when the backend sends {reason, message}", () => {
    expect(errorDetail({ detail: { reason: "unknown_tag", message: "-Q1 kommt im Signalweg nicht vor" } }, response)).toBe("-Q1 kommt im Signalweg nicht vor");
  });

  it("keeps a text detail and falls back to status and status text", () => {
    expect(errorDetail({ detail: "Maschine nicht gefunden" }, response)).toBe("Maschine nicht gefunden");
    expect(errorDetail(null, response)).toBe("404 Not Found");
    expect(errorDetail({}, response)).toBe("404 Not Found");
  });
});

describe("request errors", () => {
  it("throws the message of an object detail instead of [object Object]", async () => {
    respond(404, { detail: { reason: "no_sources", message: "Keine Tabellen und keine Leitungen im Plan gefunden" } }, "Not Found");
    await expect(signalPath("-K1", "s-1")).rejects.toThrow("Keine Tabellen und keine Leitungen im Plan gefunden");
  });

  it("does the same for the 409 of plan-read", async () => {
    respond(409, { detail: { reason: "no_model", message: "Kein Modell eingerichtet" } }, "Conflict");
    await expect(api.planRead("s-1", true)).rejects.toThrow("Kein Modell eingerichtet");
  });

  it("keeps text details and the status fallback as before", async () => {
    respond(400, { detail: "Ungültige Anfrage" });
    await expect(api.listSources()).rejects.toThrow("Ungültige Anfrage");
    respond(500, null, "Internal Server Error");
    await expect(api.listSources()).rejects.toThrow("500 Internal Server Error");
  });
});

describe("Build ohne Backend (leere NEXT_PUBLIC_API_URL)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("fails at once with NO_BACKEND and never calls fetch", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.resetModules();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { api: offlineApi, NO_BACKEND } = await import("./api");
    await expect(offlineApi.health()).rejects.toThrow(NO_BACKEND);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
