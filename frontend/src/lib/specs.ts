/** Kennzahlen einer Maschine: Darstellung der Quelle. */

/** Quelle einer Kennzahl als Link (nur gueltige http(s)-URL), sonst null fuer Klartext wie "Richtwert". */
export function sourceLink(source: string): { href: string; host: string } | null {
  if (!/^https?:\/\//.test(source)) return null;
  try {
    const url = new URL(source);
    if (!url.hostname) return null;
    return { href: source, host: url.hostname.replace(/^www\./, "") };
  } catch {
    return null;
  }
}
