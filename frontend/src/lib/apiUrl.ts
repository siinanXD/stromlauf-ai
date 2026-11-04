/**
 * API-Adresse fuer den oeffentlichen Build (SIN-1522). NEXT_PUBLIC_* landet im Browser-Bundle: eine Adresse im
 * Tailnet oder im lokalen Netz verraet den Rechnernamen und ist fuer Besucher ohnehin nicht erreichbar.
 */

const PRIVATE_SUFFIXES = [".ts.net", ".local", ".lan", ".internal", ".home.arpa"];

/** true fuer Adressen, die ein fremder Browser nicht erreicht: Loopback, privates Netz, CGNAT (Tailscale 100.64/10), Tailnet-Namen. */
export function isNonPublicApiUrl(value: string): boolean {
  let host: string;
  try {
    host = new URL(value).hostname.toLowerCase();
  } catch {
    return true;
  }
  if (host === "localhost" || host === "[::1]" || PRIVATE_SUFFIXES.some((suffix) => host.endsWith(suffix))) return true;
  const octets = host.split(".").map(Number);
  if (octets.length !== 4 || octets.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) return false;
  const [a, b] = octets;
  return a === 10 || a === 127 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127);
}

/**
 * Wert fuer NEXT_PUBLIC_API_URL im Vercel-Build: nur eine oeffentliche Adresse bleibt, sonst "" (= kein Backend).
 * Ausserhalb von Vercel (Compose, lokal, CI) gilt die Adresse unveraendert.
 */
export function publicBuildApiUrl(value: string | undefined, onVercel: boolean): string | undefined {
  if (!onVercel) return value;
  return value && !isNonPublicApiUrl(value) ? value : "";
}
