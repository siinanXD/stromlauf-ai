import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AnswerError, describeChatError } from "./chatError";

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
