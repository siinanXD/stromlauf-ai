/**
 * API-Adresse fuer den oeffentlichen Build (SIN-1522). NEXT_PUBLIC_* landet im Browser-Bundle: eine Adresse im
 * Tailnet oder im lokalen Netz verraet den Rechnernamen und ist fuer Besucher ohnehin nicht erreichbar.
 */

const PRIVATE_SUFFIXES = [".ts.net", ".local", ".lan", ".internal", ".home.arpa"];

/** true fuer Adressen, die ein fremder Browser nicht erreicht: Loopback, privates Netz, Link-local, CGNAT (Tailscale 100.64/10), Tailnet-Namen, IPv6 ausserhalb von 2000::/3. */
export function isNonPublicApiUrl(value: string): boolean {
  let host: string;
  try {
    host = new URL(value).hostname.toLowerCase();
  } catch {
    return true;
  }
  if (host === "localhost" || PRIVATE_SUFFIXES.some((suffix) => host.endsWith(suffix))) return true;
  // Global routbar ist nur 2000::/3; Loopback, ULA (Tailscale fd7a::), Link-local und IPv4-gemappt liegen ausserhalb.
  if (host.startsWith("[")) return !/^\[[23][0-9a-f]{3}:/.test(host);
  const octets = host.split(".").map(Number);
  if (octets.length !== 4 || octets.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) return false;
  const [a, b] = octets;
  return a === 10 || a === 127 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254) || (a === 100 && b >= 64 && b <= 127);
}

/**
 * Wert fuer NEXT_PUBLIC_API_URL im Vercel-Build: nur eine oeffentliche Adresse bleibt, sonst "" (= kein Backend).
 * Ausserhalb von Vercel (Compose, lokal, CI) gilt die Adresse unveraendert.
 */
export function publicBuildApiUrl(value: string | undefined, onVercel: boolean): string | undefined {
  if (!onVercel) return value;
  return value && !isNonPublicApiUrl(value) ? value : "";
}
