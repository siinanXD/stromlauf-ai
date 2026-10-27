/**
 * Agent-Testnutzer (SIN-1102): Sitzung ohne Passwort fuer Playwright.
 * Magic-Link anfordern (das Backend braucht dafuer AUTH_DEV_LINK=true, nur Test-/Staging-Umgebung), Link gegen das JWT
 * tauschen und daraus einen `storageState` bauen (localStorage-Eintrag wie `lib/auth.ts`). Nur im Job verwenden, die
 * Datei nie als Artefakt hochladen. Das Konto ist per AGENT_TEST_EMAIL im Backend auf Lesen beschraenkt.
 */

export const TOKEN_KEY = "stromlauf.token"; // wie lib/auth.ts

export type StorageState = {
  cookies: never[];
  origins: { origin: string; localStorage: { name: string; value: string }[] }[];
};

type Fetch = typeof fetch;

async function post<T>(fetchImpl: Fetch, url: string, body: unknown): Promise<T> {
  const response = await fetchImpl(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`POST ${url}: HTTP ${response.status}`);
  return (await response.json()) as T;
}

export function tokenFromLink(link: string): string {
  const token = new URL(link).searchParams.get("token");
  if (!token) throw new Error("Link ohne token");
  return token;
}

export async function buildStorageState(options: {
  apiUrl: string;
  baseUrl: string;
  email: string;
  fetchImpl?: Fetch;
}): Promise<StorageState> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const api = options.apiUrl.replace(/\/$/, "");
  const link = await post<{ dev_link: string | null }>(fetchImpl, `${api}/api/auth/magic-link`, { email: options.email });
  if (!link.dev_link) throw new Error("Kein dev_link in der Antwort: das Backend braucht AUTH_DEV_LINK=true");
  const session = await post<{ token: string }>(fetchImpl, `${api}/api/auth/exchange`, { token: tokenFromLink(link.dev_link) });
  return {
    cookies: [],
    origins: [{ origin: new URL(options.baseUrl).origin, localStorage: [{ name: TOKEN_KEY, value: session.token }] }],
  };
}
