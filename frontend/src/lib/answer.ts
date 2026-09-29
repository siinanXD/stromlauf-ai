/** Chat-Antworten zerlegen: Belege [[Datei|Ort]] und die festen Abschnitte aus dem System-Prompt. */

import type { CitationCheck, CitationsValid } from "./api";

export interface Citation {
  index: number;
  filename: string;
  loc: string;
}

export interface Sections {
  kurz?: string;
  pruefen?: string;
  details?: string;
  sicherheit?: string;
  /** Text ausserhalb der bekannten Abschnitte; bei alten Antworten die ganze Antwort. */
  frei: string;
}

const MARKER = /\[\[([^\]|]+)\|([^\]]+)\]\]/g;
const HEADING = /^##\s+(Kurzantwort|Prüfen|Pruefen|Details|Sicherheit)\s*$/gim;
const SECTION_KEY: Record<string, keyof Omit<Sections, "frei">> = {
  kurzantwort: "kurz",
  prüfen: "pruefen",
  pruefen: "pruefen",
  details: "details",
  sicherheit: "sicherheit",
};

const DOC_LABELS: Record<string, string> = {
  schematic: "Stromlaufplan",
  bom: "Stückliste",
  terminal_plan: "Klemmenplan",
  plc_program: "SPS-Programm",
  plc_symbols: "Symboltabelle",
  manual: "Handbuch",
};

/** Ersetzt Belege durch Links "cite:N" (gleiche Belege teilen sich N); unfertige Marker bleiben Text. */
export function parseCitations(markdown: string): { markdown: string; citations: Citation[] } {
  const citations: Citation[] = [];
  const replaced = markdown.replace(MARKER, (_, rawFile: string, rawLoc: string) => {
    const filename = rawFile.trim();
    const loc = rawLoc.trim();
    let citation = citations.find((c) => c.filename === filename && c.loc === loc);
    if (!citation) {
      citation = { index: citations.length, filename, loc };
      citations.push(citation);
    }
    return `[${loc}](cite:${citation.index})`;
  });
  return { markdown: replaced, citations };
}

/** Teilt nach ## Kurzantwort / Prüfen / Details / Sicherheit; ohne diese Gliederung alles in "frei". */
export function splitSections(markdown: string): Sections {
  const matches = [...markdown.matchAll(HEADING)];
  if (matches.length === 0) return { frei: markdown };
  const sections: Sections = { frei: markdown.slice(0, matches[0].index).trim() };
  matches.forEach((match, i) => {
    const start = match.index! + match[0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index : markdown.length;
    const key = SECTION_KEY[match[1].toLowerCase()];
    const body = markdown.slice(start, end).trim();
    sections[key] = sections[key] ? `${sections[key]}\n\n${body}` : body;
  });
  return sections;
}

/** "Stromlaufplan /3.8"; ohne Dokumenttyp der Dateiname ohne Nummer und Endung. */
export function citationLabel(citation: Citation, docType?: string): string {
  const short =
    (docType && DOC_LABELS[docType]) ||
    citation.filename.replace(/\.[^.]+$/, "").replace(/^\d+[_-]/, "").replace(/_/g, " ");
  return `${short} ${citation.loc}`;
}

/** Seite oder Stromlaufplan-Verweis aus dem Ort; leer, wenn nichts Anspringbares drinsteht. */
export function refOf(loc: string): { ref?: string; page?: number } {
  const sheet = loc.match(/\/\d+\.\d+/);
  if (sheet) return { ref: sheet[0] };
  const page = loc.match(/S\.\s*(\d+)/);
  if (page) return { ref: `S. ${page[1]}`, page: Number(page[1]) };
  return {};
}

/** Pruefergebnis des Backends zu einem Beleg (Datei ohne Gross/Klein, Ort genau); undefined ohne meta. */
export function citationCheckFor(checks: CitationCheck[] | undefined, citation: Citation): CitationCheck | undefined {
  if (!checks) return undefined;
  const file = citation.filename.toLowerCase();
  return checks.find((c) => c.file.toLowerCase() === file && c.locator === citation.loc);
}

/** Fuss der Antwort: "Belege: 5 von 6 gültig" bzw. mit nicht pruefbaren Orten
 * "Belege: 4 von 4 geprüft gültig, 2 nicht prüfbar" (ungepruefte zaehlen im Backend als gueltig, sind aber
 * nicht belegt und werden hier nicht als gueltig ausgegeben); leer ohne Belege. */
export function citationsValidLabel(valid: CitationsValid | undefined): string {
  if (!valid || valid.total === 0) return "";
  const unchecked = valid.total - valid.checked;
  if (unchecked > 0) {
    return `Belege: ${valid.valid - unchecked} von ${valid.checked} geprüft gültig, ${unchecked} nicht prüfbar`;
  }
  return `Belege: ${valid.valid} von ${valid.total} gültig`;
}

/** Erstes Geraete-Kennzeichen (-M1, -K12) eines Textes; Klemmen (-X1:5) zaehlen nicht. */
export function deviceTagOf(text: string): string | null {
  const match = text.toUpperCase().match(/(?<![\w-])-[A-Z]{1,3}\d{1,4}(?![\d:.])/);
  return match ? match[0] : null;
}
