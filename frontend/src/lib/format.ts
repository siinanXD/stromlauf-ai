/** Anzeigeformate: deutsche Zahlen, Euro, KI-Kosten aus dem Kostenbuch. */

export const num = (value: number, digits = 0) =>
  value.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const eur = (value: number) => `${num(value, 2)} €`;

/** KI-Kosten aus dem Kostenbuch (Cent, Listenpreise 1:1 in Euro): "≈ 0,02 €", unter einem Zehntelcent "< 0,01 €". */
export function costText(cents: number): string {
  if (cents <= 0) return "0,00 €";
  if (cents < 0.5) return "< 0,01 €";
  return `≈ ${eur(cents / 100)}`;
}
