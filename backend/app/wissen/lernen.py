"""Belegte Sätze aus Chat-Antworten lernen (rein, ohne Datenbank und Modellaufruf)."""

import json

MAX_LAUF = 5
MAX_CHAT = 2
MAX_PROMPT = 30
MAX_ZEICHEN = 300


def belege_nummerieren(antworten: list[dict], erlaubte_dokumente: set[str]) -> list[dict]:
    """Quellen aller Antworten, ohne Dubletten und fremde Dokumente, ab 1 nummeriert."""
    belege: list[dict] = []
    gesehen: set[tuple] = set()
    for antwort in antworten:
        for quelle in antwort.get("sources", []):
            dokument = quelle.get("document_id")
            seite = quelle.get("page")
            if dokument not in erlaubte_dokumente or (dokument, seite) in gesehen:
                continue
            gesehen.add((dokument, seite))
            belege.append({
                "nr": len(belege) + 1,
                "document_id": dokument,
                "filename": quelle.get("filename", ""),
                "page": seite,
            })
    return belege


def _beleg_zeile(beleg: dict) -> str:
    seite = f" S. {beleg['page']}" if beleg["page"] is not None else ""
    return f"[{beleg['nr']}] {beleg['filename']}{seite}"


def lern_prompt(kontext: str, antworten: list[dict], belege: list[dict], max_saetze: int) -> str:
    """Anweisung an das Modell: belegte Tatsachen über die Maschine als JSON-Liste."""
    teile = [
        f"Maschine: {kontext}",
        "",
        f"Formuliere höchstens {max_saetze} kurze Sätze. Jeder Satz hält genau eine "
        "Tatsache über diese Maschine fest, die sich nur aus den folgenden Antworten ergibt. "
        "Gib zu jedem Satz die Nummern der Belege an, die ihn stützen (Liste unten).",
        'Antworte genau im Format [{"text": "...", "belege": [1, 3]}]. '
        "Gibt es nichts Belegtes zu lernen, antworte mit [].",
        "",
        "Antworten:",
    ]
    for antwort in antworten:
        teile.append(f"Frage: {antwort.get('question', '')}")
        teile.append(f"Antwort: {antwort.get('answer_md', '')}")
        teile.append("")
    teile.append("Belege:")
    teile.extend(_beleg_zeile(b) for b in belege)
    return "\n".join(teile)


def parse_saetze(text: str, belege: list[dict], max_saetze: int) -> list[dict]:
    """Erstes JSON-Array aus der Modellantwort; nur Sätze mit mindestens einem gültigen Beleg."""
    anfang, ende = text.find("["), text.rfind("]")
    if anfang < 0 or ende < anfang:
        return []
    try:
        daten = json.loads(text[anfang : ende + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(daten, list):
        return []
    nach_nr = {b["nr"]: b for b in belege}
    saetze: list[dict] = []
    for eintrag in daten:
        if len(saetze) >= max_saetze:
            break
        if not isinstance(eintrag, dict):
            continue
        satz = eintrag.get("text")
        nummern = eintrag.get("belege")
        if not isinstance(satz, str) or not isinstance(nummern, list):
            continue
        satz = " ".join(satz.split())
        if not satz or len(satz) > MAX_ZEICHEN:
            continue
        gueltig: list[dict] = []
        for nr in nummern:
            beleg = nach_nr.get(nr) if isinstance(nr, int) and not isinstance(nr, bool) else None
            if beleg is None:
                continue
            ref = {"document_id": beleg["document_id"], "page": beleg["page"]}
            if ref not in gueltig:
                gueltig.append(ref)
        if gueltig:
            saetze.append({"text": satz, "belege": gueltig})
    return saetze


def normalisiert(text: str) -> str:
    """Vergleichsform: klein, Leerraum zusammengezogen, Satzzeichen am Ende weg."""
    return " ".join(text.lower().split()).rstrip(".!?:; ")


def ohne_dubletten(neu: list[dict], vorhanden: list[str]) -> list[dict]:
    """Entfernt Sätze, die schon vorhanden (normalisiert) oder früher in `neu` stehen."""
    gesehen = set(vorhanden)
    ergebnis: list[dict] = []
    for satz in neu:
        schluessel = normalisiert(satz["text"])
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        ergebnis.append(satz)
    return ergebnis


def prompt_block(saetze: list[str]) -> str:
    """Kontextblock für Prompts; leer, wenn nichts gelernt wurde."""
    if not saetze:
        return ""
    zeilen = "\n".join(f"- {s}" for s in saetze)
    return (
        "\n<kontext>\nBisher über diese Maschine gelernt "
        "(aus Dokumenten belegt, vom Menschen geprüfte zuerst):\n"
        f"{zeilen}\n</kontext>\n"
    )
