/** Anmeldung im Browser: JWT aus POST /api/auth/exchange, im localStorage, als Bearer an die API. */

const TOKEN_KEY = "stromlauf.token";
let memoryToken: string | null = null; // Fallback ohne localStorage (SSR, Tests)

function storage(): Storage | null {
  try {
    return typeof window !== "undefined" && window.localStorage ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  const store = storage();
  return store ? store.getItem(TOKEN_KEY) : memoryToken;
}

export function setToken(token: string): void {
  memoryToken = token;
  storage()?.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  memoryToken = null;
  storage()?.removeItem(TOKEN_KEY);
}

/** Ablauf aus dem JWT lesen (exp in Sekunden); ungueltig oder abgelaufen = false. */
export function tokenValid(token: string | null, now: number = Date.now()): boolean {
  if (!token) return false;
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  try {
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" && payload.exp * 1000 > now;
  } catch {
    return false;
  }
}

/** Wohin nach dem Logout / bei 401: die Login-Seite, ausser wir sind schon dort. */
export function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname.startsWith("/login")) return;
  window.location.href = "/login"; // voller Reload: Login liegt ausserhalb des angemeldeten Zustands
}
