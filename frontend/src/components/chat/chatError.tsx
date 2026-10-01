/**
 * Fehler einer Antwort fuer Menschen: ein Satz statt Server- oder Ausnahmetext (keine Umgebungsvariablen,
 * Dateien, Ports, Klassennamen). Der Rohtext steht nur zugeklappt unter "Details".
 */
import type { Health } from "@/lib/api";

const MISSING_KEY = /_API_KEY|api[ _-]?key|\.env\b|schl(ü|ue)ssel (fehlt|nicht)|kein(en)? schl(ü|ue)ssel|missingkeyerror/i;
const BUDGET = /monatslimit|budget/i;
const NETWORK = /failed to fetch|networkerror|load failed|network request failed|nicht erreichbar/i;
const TIMEOUT = /zeitlimit|timeout|timed out|zu lange/i;

export interface ChatErrorText {
  /** Satz fuer die Fehlerzeile. */
  message: string;
  /** Rohtext fuer "Details"; leer, wenn er nichts hinzufuegt. */
  details: string;
}

/**
 * faultList: im Maschinen-Chat steht die Fehlerliste ohne Modell darueber und funktioniert trotzdem.
 * answer=false: Hinweis ueber dem Chat statt Fehler einer Antwort (es gibt noch keine Antwort, die scheitern koennte).
 */
export function describeChatError(
  raw: string | null | undefined,
  { faultList = false, answer = true }: { faultList?: boolean; answer?: boolean } = {},
): ChatErrorText {
  const text = (raw ?? "").trim();
  let message: string;
  if (MISSING_KEY.test(text))
    message = faultList
      ? "Der KI-Zugang ist nicht eingerichtet. Die Fehlerliste oben funktioniert trotzdem."
      : answer
        ? "Der KI-Zugang ist nicht eingerichtet."
        : "Der KI-Zugang ist nicht eingerichtet. Hochladen und Verwalten funktionieren trotzdem.";
  else if (BUDGET.test(text)) message = "Das KI-Monatslimit ist erreicht. Neue Antworten gibt es ab dem nächsten Monat oder mit höherem Limit.";
  else if (NETWORK.test(text)) message = answer ? "Keine Verbindung zum Server. Die Antwort ist fehlgeschlagen." : "Keine Verbindung zum Server.";
  else if (TIMEOUT.test(text)) message = "Die Antwort hat zu lange gedauert und wurde abgebrochen.";
  else message = answer ? "Die Antwort ist fehlgeschlagen." : "Etwas ist schiefgelaufen.";
  return { message, details: text && text !== message ? text : "" };
}

function Details({ text }: { text: string }) {
  return (
    <details className="group text-xs text-muted-foreground">
      <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-1 hover:text-foreground">Details</summary>
      <p className="break-words font-mono">{text}</p>
    </details>
  );
}

/** Fehlerzeile unter der Antwort: nur sie ist rot, die Details bleiben grau und zugeklappt. */
export function AnswerError({ raw, faultList = false }: { raw: string; faultList?: boolean }) {
  const { message, details } = describeChatError(raw, { faultList });
  return (
    <div className="space-y-1" data-testid="answer-error">
      <p className="border border-danger/40 px-3 py-2 text-sm text-danger" role="alert">
        {message}
      </p>
      {details && <Details text={details} />}
    </div>
  );
}

/**
 * Rohtext fuer den Hinweis ueber dem werksweiten Chat: Server nicht erreichbar oder kein Modell-Schluessel.
 * Nur fuer "Details"; angezeigt wird der Satz aus describeChatError.
 */
export function homeNotice({ health, unreachable }: { health: Pick<Health, "api_key_configured"> | null; unreachable: string | null }): string | null {
  if (unreachable !== null) return unreachable;
  if (health && !health.api_key_configured) return "ANTHROPIC_API_KEY fehlt: In .env eintragen und das Backend neu starten. Upload und Verwaltung funktionieren bereits.";
  return null;
}

/** Hinweis ueber dem Chat (kein Antwortfehler): Satz fuer Menschen, Rohtext zugeklappt unter "Details". */
export function ChatNotice({ raw }: { raw: string }) {
  const { message, details } = describeChatError(raw, { answer: false });
  return (
    <div className="space-y-0.5" role="status" data-testid="chat-notice">
      <p>{message}</p>
      {details && <Details text={details} />}
    </div>
  );
}
