"""Treffer in Fehlerlisten und erledigten Stoerfaellen zu einer Meldung, ohne Modell.

Dieselbe Trefferlogik fuer das Agenten-Werkzeug search_faults und GET /api/machines/{id}/fault-hits. Eine Meldung
trifft einen Eintrag, wenn

- sie woertlich darin steht (wie bisher, Schreibweise egal) oder als Kennzeichen zu seinen tags gehoert,
- ein Kennzeichen aus der Meldung zu seinen tags gehoert ("K1 zieht nicht" trifft einen Eintrag mit -K1),
- ein Wort der Meldung darin vorkommt. Meldungen vom Bedienpanel nennen das Symptom selten am Stueck:
  "Stoerung Motorschutz Foerderband" soll "Motorschutz -F2 ausgeloest" finden. Als Wort zaehlt, was mindestens
  MIN_WORD Buchstaben hat und kein Fuellwort ist ("Stoerung", "nicht"); Codes mit Ziffern ("F03", "E-F2") zaehlen
  ab zwei Zeichen. Ein Wort trifft am Wortanfang ("Motor" in "Motorstrom"), ab MIN_INFIX Buchstaben auch im Wort
  ("Schutz" in "Motorschutz"); so trifft "Halt" nicht "einschalten".

Umlaute zaehlen wie ihre Umschreibung (ae, oe, ue, ss), denn Fehlerlisten sind oft ohne Umlaute gepflegt. Die
Punktzahl ordnet die Treffer: woertlich oder als Kennzeichen vor einzelnen Woertern.
"""

import re

from app.ingestion.tags import extract_tags, normalize_tag

FIELDS = ("code", "symptom", "cause", "fix", "doc_ref")
MIN_WORD = 4
MIN_INFIX = 6
WHOLE = 100  # Meldung woertlich oder als Kennzeichen
TAG = 10  # je Kennzeichen der Meldung unter den tags des Eintrags
WORD = 1  # je Wort der Meldung im Text des Eintrags
_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_EDGE = ".,;:!?()[]{}\"'„“”«»/"
# Woerter, die in fast jeder Meldung stehen und nichts ueber die Ursache sagen (in Umschreibung, klein)
STOPWORDS = frozenset(
    """
    stoerung stoerungen stoermeldung fehler fehlermeldung meldung meldungen problem probleme defekt ausfall
    maschine anlage bitte hilfe frage error fault
    nicht kein keine keinen keiner ohne wird werden wurde wurden sind habe haben hatte hatten beim nach oder
    aber auch noch dann wenn weil dass eine einer einem einen eines dieser diese dieses diesem diesen mehr immer
    schon sehr wieder seit heute gerade jetzt mein meine unser unsere warum wieso weshalb welche welcher welches
    woran liegt kann koennen muss soll sollte ueber unter zwischen durch fuer gegen mich sich etwas alles alle
    geht gehen kommt zeigt macht hier dort denn doch also ganz with from this that
    """.split()
)


def fold(text: str) -> str:
    """Klein, Umlaute umschrieben, Leerraum zusammengefasst."""
    return " ".join(text.lower().translate(_FOLD).split())


def _terms(query: str) -> list[str]:
    """Woerter und Codes der Meldung, die einzeln zaehlen (gefaltet, ohne Doppelte)."""
    terms: list[str] = []
    for raw in fold(query).split():
        token = raw.strip(_EDGE)
        if re.search(r"\d", token) and re.search(r"[a-z]", token):
            if len(token.strip("-")) >= 2:
                terms.append(token)
            continue
        terms += [
            w for w in re.findall(r"[a-z]+", token) if len(w) >= MIN_WORD and w not in STOPWORDS
        ]
    return list(dict.fromkeys(terms))


def _tags(query: str) -> set[str]:
    """Kennzeichen der Meldung in Index-Schreibweise: gefundene ("-K1", "E0.2") und kurze Codes ("K1" -> "-K1")."""
    found = {tag.tag for tag in extract_tags(query)}
    for raw in query.split():
        token = raw.strip(_EDGE)
        if re.search(r"\d", token) and re.search(r"[A-Za-z]", token) and len(token) <= 12:
            found.add(normalize_tag(token))
    return found


class FaultQuery:
    """Eine Meldung, einmal zerlegt und gegen beliebig viele Eintraege geprueft."""

    def __init__(self, query: str) -> None:
        self.text = query
        self.needle = fold(query)
        self.normalized = normalize_tag(query) if self.needle else ""
        self.tags = _tags(query) if self.needle else set()
        self.terms = _terms(query)
        self._patterns = [
            re.compile(re.escape(t) if len(t) >= MIN_INFIX else rf"(?<![a-z0-9]){re.escape(t)}")
            for t in self.terms
        ]

    @property
    def empty(self) -> bool:
        return not self.needle

    def score(self, fault: dict) -> int:
        """0 = kein Treffer; sonst hoeher, je genauer die Meldung passt."""
        if self.empty:
            return 0
        haystack = fold(" ".join(str(fault.get(k) or "") for k in FIELDS))
        fault_tags = {normalize_tag(str(t)) for t in fault.get("tags") or [] if str(t).strip()}
        score = WHOLE if self.needle in haystack or self.normalized in fault_tags else 0
        score += TAG * len(self.tags & fault_tags)
        score += WORD * sum(1 for pattern in self._patterns if pattern.search(haystack))
        return score


def fault_score(fault: dict, query: str) -> int:
    return FaultQuery(query).score(fault)


def fault_matches(fault: dict, query: str) -> bool:
    """Treffer im Sinne des Moduls; eine leere Meldung passt zu allem (Werkzeug ohne Suchwort)."""
    parsed = FaultQuery(query)
    return parsed.empty or parsed.score(fault) > 0
