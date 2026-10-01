import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AnswerError, ChatNotice, describeChatError, homeNotice } from "./chatError";

const MISSING_KEY = "ANTHROPIC_API_KEY fehlt fuer Modell 'claude-sonnet-5'. In .env eintragen und Backend neu starten.";

describe("describeChatError", () => {
  it("turns a missing model key into a user sentence; the machine chat points to the fault list", () => {
    expect(describeChatError(MISSING_KEY, { faultList: true })).toEqual({
      message: "Der KI-Zugang ist nicht eingerichtet. Die Fehlerliste oben funktioniert trotzdem.",
      details: MISSING_KEY,
    });
    expect(describeChatError("OPENAI_API_KEY fehlt").message).toBe("Der KI-Zugang ist nicht eingerichtet.");
  });

  it("says the answer failed for anything else and keeps the raw text only as details", () => {
    expect(describeChatError("RuntimeError: Traceback in app/agent/graph.py line 12")).toEqual({
      message: "Die Antwort ist fehlgeschlagen.",
      details: "RuntimeError: Traceback in app/agent/graph.py line 12",
    });
    expect(describeChatError("500 Internal Server Error").message).toBe("Die Antwort ist fehlgeschlagen.");
    expect(describeChatError("")).toEqual({ message: "Die Antwort ist fehlgeschlagen.", details: "" });
  });

  it("names budget, network and timeout in plain words", () => {
    expect(describeChatError("402: KI-Monatslimit erreicht").message).toMatch(/^Das KI-Monatslimit ist erreicht/);
    expect(describeChatError("Failed to fetch").message).toBe("Keine Verbindung zum Server. Die Antwort ist fehlgeschlagen.");
    expect(describeChatError("Zeitlimit der Antwort erreicht").message).toBe("Die Antwort hat zu lange gedauert und wurde abgebrochen.");
  });
});

describe("AnswerError", () => {
  it("shows the sentence in the error line and hides the developer text behind a closed Details toggle", () => {
    const html = renderToStaticMarkup(<AnswerError raw={MISSING_KEY} faultList />);
    const line = html.match(/<p class="([^"]*)" role="alert">([^<]*)<\/p>/);
    expect(line?.[1]).toContain("text-danger");
    expect(line?.[2]).toBe("Der KI-Zugang ist nicht eingerichtet. Die Fehlerliste oben funktioniert trotzdem.");
    expect(line?.[2]).not.toMatch(/API_KEY|\.env|claude-sonnet/);
    expect(html).toMatch(/<details class="[^"]*text-muted-foreground[^"]*"><summary[^>]*>Details<\/summary>/);
    expect(html).not.toContain("<details open");
  });
});

describe("Hinweis über dem werksweiten Chat (Startseite)", () => {
  it("builds the raw notice from health or an unreachable server, nothing when all is fine", () => {
    expect(homeNotice({ health: { api_key_configured: true }, unreachable: null })).toBeNull();
    expect(homeNotice({ health: null, unreachable: null })).toBeNull();
    expect(homeNotice({ health: { api_key_configured: false }, unreachable: null })).toContain("ANTHROPIC_API_KEY");
    expect(homeNotice({ health: null, unreachable: "Backend unter http://localhost:8010 nicht erreichbar: Failed to fetch" })).toContain("8010");
  });

  it("shows a sentence without the fault list for a missing key; env var and file only under Details", () => {
    const html = renderToStaticMarkup(<ChatNotice raw={homeNotice({ health: { api_key_configured: false }, unreachable: null })!} />);
    const sentence = html.match(/role="status"[^>]*><p>([^<]*)<\/p>/)?.[1] ?? "";
    expect(sentence).toBe("Der KI-Zugang ist nicht eingerichtet. Hochladen und Verwalten funktionieren trotzdem.");
    expect(sentence).not.toMatch(/Fehlerliste|API_KEY|\.env/);
    expect(html).toMatch(/<details[^>]*><summary[^>]*>Details<\/summary><p[^>]*>ANTHROPIC_API_KEY fehlt/);
    expect(html).not.toContain("<details open");
  });

  it("says there is no connection for an unreachable server, port and address only under Details", () => {
    const html = renderToStaticMarkup(<ChatNotice raw="Backend unter http://localhost:8010 nicht erreichbar: Failed to fetch" />);
    const sentence = html.match(/role="status"[^>]*><p>([^<]*)<\/p>/)?.[1] ?? "";
    expect(sentence).toBe("Keine Verbindung zum Server.");
    expect(sentence).not.toMatch(/8010|localhost|Antwort/);
  });

  it("never mentions the fault list in the global chat's answer errors", () => {
    expect(describeChatError("ANTHROPIC_API_KEY fehlt").message).toBe("Der KI-Zugang ist nicht eingerichtet.");
  });
});
