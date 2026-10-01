import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, type Conversation } from "@/lib/api";

import { clearInitialLoad, incidentsFor, startInitialLoad, takeIncidents, takeMachine } from "./initialLoad";

const SOURCE = "s-fb01";
const MINE: Conversation = { id: "conv-1", title: "-K1 zieht nicht an", source_ids: [SOURCE], updated_at: "2026-09-29T10:00:00Z" };
const GLOBAL: Conversation = { id: "conv-7", title: "Frage über alles", source_ids: [], updated_at: "2026-09-29T11:00:00Z" };
const OTHER: Conversation = { id: "conv-8", title: "Presse P-02", source_ids: ["s-p02"], updated_at: "2026-09-29T12:00:00Z" };

type Route = (url: URL) => { status: number; body: unknown };

function stubFetch(route: Route) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const { status, body } = route(new URL(String(input)));
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const paths = (fetchMock: ReturnType<typeof stubFetch>) => fetchMock.mock.calls.map(([input]) => { const u = new URL(String(input)); return `${u.pathname}${u.search}`; });

beforeEach(() => clearInitialLoad());
afterEach(() => vi.unstubAllGlobals());

describe("listConversationsForMachine", () => {
  it("returns the incidents of the machine", async () => {
    stubFetch(() => ({ status: 200, body: [MINE] }));
    await expect(api.listConversationsForMachine("m-fb01")).resolves.toEqual([MINE]);
  });

  it("returns null for an older backend (404 or 422) and throws on other errors", async () => {
    stubFetch(() => ({ status: 422, body: { detail: [{ msg: "unknown" }] } }));
    await expect(api.listConversationsForMachine("m-fb01")).resolves.toBeNull();
    stubFetch(() => ({ status: 404, body: { detail: "Not Found" } }));
    await expect(api.listConversationsForMachine("m-fb01")).resolves.toBeNull();
    stubFetch(() => ({ status: 500, body: { detail: "kaputt" } }));
    await expect(api.listConversationsForMachine("m-fb01")).rejects.toThrow("kaputt");
  });
});

describe("initial load of the machine page", () => {
  it("asks for machine and incidents at the same time, before anything is awaited", () => {
    vi.stubGlobal("window", {});
    const fetchMock = stubFetch((url) => (url.pathname.endsWith("/conversations") ? { status: 200, body: [MINE] } : { status: 200, body: { id: "m-fb01" } }));
    startInitialLoad("m-fb01");
    expect(paths(fetchMock)).toEqual(["/api/machines/m-fb01", "/api/conversations?machine_id=m-fb01"]);
    // idempotent: ein zweiter Aufruf (StrictMode, erneutes Rendern) fragt nicht noch einmal
    startInitialLoad("m-fb01");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("hands each started request out once, later calls fetch fresh data", async () => {
    vi.stubGlobal("window", {});
    const fetchMock = stubFetch((url) => (url.pathname.endsWith("/conversations") ? { status: 200, body: [MINE] } : { status: 200, body: { id: "m-fb01" } }));
    startInitialLoad("m-fb01");
    await expect(takeIncidents("m-fb01")).resolves.toEqual([MINE]);
    await expect(takeMachine("m-fb01")).resolves.toEqual({ id: "m-fb01" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await takeIncidents("m-fb01");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not fetch while rendering on the server", () => {
    const fetchMock = stubFetch(() => ({ status: 200, body: [] }));
    startInitialLoad("m-fb01");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("incidentsFor", () => {
  it("falls back to source_id when the backend does not know machine_id", async () => {
    const fetchMock = stubFetch(() => ({ status: 200, body: [MINE] }));
    await expect(incidentsFor(Promise.resolve(null), SOURCE)).resolves.toEqual([MINE]);
    expect(paths(fetchMock)).toEqual([`/api/conversations?source_id=${SOURCE}`]);
  });

  it("keeps only incidents of this source when a backend ignores machine_id and sends every chat", async () => {
    await expect(incidentsFor(Promise.resolve([GLOBAL, MINE, OTHER]), SOURCE)).resolves.toEqual([MINE]);
  });
});
