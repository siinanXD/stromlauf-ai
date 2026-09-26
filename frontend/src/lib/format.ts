/** Anzeigeformate fuer Planung: deutsche Zahlen, Euro, Zeitpunkte, Dauern. */

import { dayLabel } from "./timeline";

export const num = (value: number, digits = 0) =>
  value.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });

const DIGITS: Record<string, number> = { t: 2, kg: 1, "m³": 1 };

export const qtyText = (value: number, unit: string) => `${num(value, DIGITS[unit] ?? 0)} ${unit}`.trim();

export const eur = (value: number) => `${num(value, 2)} €`;

export const whenText = (iso: string) => {
  const d = new Date(iso);
  return `${dayLabel(d)} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

export function minutesText(minutes: number): string {
  const total = Math.round(minutes);
  if (total < 60) return `${total} min`;
  if (total < 24 * 60) return `${Math.floor(total / 60)} h ${String(total % 60).padStart(2, "0")} min`;
  const hours = Math.floor(total / 60);
  return `${Math.floor(hours / 24)} d ${hours % 24} h`;
}

const PLURAL: Record<string, string> = { Paket: "Pakete", Box: "Boxen", Karton: "Kartons", Rolle: "Rollen" };
export const plural = (unitName: string) => PLURAL[unitName] ?? unitName;
