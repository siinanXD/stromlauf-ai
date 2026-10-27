"""Demo-Modus (`DEMO_MODE=true`): oeffentliche Instanz ohne Schreibzugriffe und mit Rate-Limit je IP.

- Alle schreibenden Methoden unter /api liefern 403, ausser Chat (`/api/chat`), Beleg-Pruefung (liest nur)
  und der Login-Fluss. Damit entfallen Upload, Loeschen und jede Aenderung der Daten.
- Je IP und Minute sind `DEMO_RATE_LIMIT` Anfragen erlaubt, davon `DEMO_CHAT_RATE_LIMIT` Chat-Fragen
  (Chat kostet Modell-Token); darueber 429 mit `Retry-After`. Zaehler im Prozess, kein Redis.
  Hinter einem Proxy `DEMO_TRUST_PROXY=true`: dann zaehlt das letzte Glied von `X-Forwarded-For`.
- Beim Start legt `seed_example` die Beispiel-Maschine FB-01 an, wenn die Instanz noch leer ist.
"""

import logging
import shutil
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
WRITE_ALLOWED = ("/api/chat", "/api/answers/validate-citations", "/api/auth/")
CHAT_PATH = "/api/chat"
WINDOW_S = 60.0

SOURCE_NAME = "Foerderband FB-01"
HALL_NAME = "Halle 1 (Beispiel)"
EXAMPLE_FILES = [
    ("01_Stromlaufplan_FB-01.pdf", "schematic"),
    ("02_Stueckliste_FB-01.xlsx", "bom"),
    ("03_Klemmenplan_FB-01.csv", "terminal_plan"),
    ("04_SPS_Programm_FB-01.awl", "plc_program"),
    ("05_Symboltabelle_FB-01.sdf", "plc_symbols"),
    ("06_Betriebsanleitung_FB-01.md", "manual"),
]
FAULTS = [
    {"code": "E-F2", "symptom": "-H2 leuchtet, Band steht, Start ohne Wirkung",
     "cause": "Motorschutz -F2 ausgeloest (E0.2 = 0)",
     "fix": "-F2 pruefen, Motorstrom -M1 messen (Nennstrom 3,5 A). Nach Abkuehlen einschalten, mit -S1 quittieren.",
     "doc_ref": "Betriebsanleitung Kap. 6, Stromlaufplan Blatt 3", "tags": ["-F2", "-M1", "-H2"]},
    {"code": "E-BLOCK", "symptom": "-H2 leuchtet nach ca. 20 s Betrieb",
     "cause": "Blockade: Teil am Einlauf -B1, aber nicht am Auslauf -B2 (Timer T5)",
     "fix": "Band auf Verklemmung pruefen, -B2 reinigen und ausrichten (Klemme -X3:6, E0.5).",
     "doc_ref": "FB10 Netzwerk 5, Betriebsanleitung Kap. 6", "tags": ["-B1", "-B2", "-X3"]},
    {"code": "E-NH", "symptom": "Start ohne Wirkung, -H1 und -H2 aus",
     "cause": "Not-Halt nicht entriegelt, -K3 ohne Freigabe (E0.3 = 0)",
     "fix": "-S3 entriegeln, 24 V an -X3:4 pruefen, beide Kanaele -S3 11/12 und 21/22 pruefen.",
     "doc_ref": "Stromlaufplan Blatt 4", "tags": ["-S3", "-K3", "-X3"]},
    {"code": "E-PH", "symptom": "-K1 zieht an, Motor brummt, dreht nicht",
     "cause": "Phase fehlt am Motorabgang",
     "fix": "Spannung an -X4:U/V/W pruefen, Motorleitung -W4 und -M1:U1/V1/W1.",
     "doc_ref": "Stromlaufplan Blatt 3", "tags": ["-X4", "-M1", "-K1"]},
]


def write_blocked(method: str, path: str) -> bool:
    if method not in WRITE_METHODS or not path.startswith("/api/"):
        return False
    return not path.startswith(WRITE_ALLOWED)


def client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy and (forwarded := request.headers.get("x-forwarded-for")):
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unbekannt"


class RateLimiter:
    """Gleitendes Fenster je Schluessel; `hit` meldet die Wartezeit in Sekunden oder 0."""

    def __init__(self, window_s: float = WINDOW_S, clock=time.monotonic):
        self.window_s = window_s
        self.clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int) -> int:
        now = self.clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, int(self.window_s - (now - hits[0])) + 1)
            hits.append(now)
            if len(self._hits) > 10_000:  # Speicher begrenzen: leere Schluessel verwerfen
                for stale in [k for k, v in self._hits.items() if not v]:
                    del self._hits[stale]
            return 0


limiter = RateLimiter()


async def demo_middleware(request: Request, call_next):
    from app.config import get_settings

    settings = get_settings()
    path, method = request.url.path, request.method
    if not settings.demo_mode or not path.startswith("/api/") or method == "OPTIONS" or path == "/api/health":
        return await call_next(request)
    ip = client_ip(request, settings.demo_trust_proxy)
    wait = limiter.hit(f"all:{ip}", settings.demo_rate_limit)
    if not wait and path == CHAT_PATH and method == "POST":
        wait = limiter.hit(f"chat:{ip}", settings.demo_chat_rate_limit)
    if wait:
        return JSONResponse(
            {"detail": "Zu viele Anfragen in der Demo. Bitte kurz warten.", "code": "rate_limited"},
            status_code=429,
            headers={"Retry-After": str(wait)},
        )
    if write_blocked(method, path):
        return JSONResponse(
            {"detail": "In der Demo sind Aenderungen und Uploads gesperrt.", "code": "demo_readonly"},
            status_code=403,
        )
    return await call_next(request)


def seed_example(example_dir: Path | None = None) -> bool:
    """Legt Quelle, Dokumente, Halle, Maschine und Fehlerliste der Beispielanlage an und liest die Dokumente
    ein (blockiert bis zum Ende). Nur auf einer Instanz ohne Wissensquelle; True, wenn angelegt."""
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import session_scope
    from app.ingestion.pipeline import detect_doc_type, ingest_document
    from app.models import Document, FaultEntry, Hall, KnowledgeSource, Machine
    from app.tenancy import DEFAULT_WORKSPACE_ID, reset_workspace, set_workspace

    settings = get_settings()
    directory = (
        example_dir or settings.demo_example_dir or Path(__file__).resolve().parents[2] / "examples" / "foerderband"
    )
    if not (directory / EXAMPLE_FILES[0][0]).exists():
        logger.warning("DEMO_MODE: Beispieldaten fehlen unter %s, keine Beispiel-Maschine", directory)
        return False
    token = set_workspace(DEFAULT_WORKSPACE_ID)
    try:
        document_ids: list[str] = []
        with session_scope() as session:
            if session.scalars(select(KnowledgeSource).limit(1)).first() is not None:
                return False
            source = KnowledgeSource(
                name=SOURCE_NAME,
                description="Beispielanlage: Stromlaufplan, Stueckliste, Klemmenplan, AWL, Symboltabelle, Anleitung",
            )
            session.add(source)
            session.flush()
            for filename, doc_type in EXAMPLE_FILES:
                document_id = uuid.uuid4().hex
                path = settings.upload_dir / f"{document_id}{Path(filename).suffix.lower()}"
                shutil.copyfile(directory / filename, path)
                session.add(
                    Document(
                        id=document_id,
                        source_id=source.id,
                        filename=filename,
                        storage_path=str(path),
                        doc_type=detect_doc_type(filename, doc_type, path),
                    )
                )
                document_ids.append(document_id)
            hall = Hall(name=HALL_NAME, description="Beispielhalle aus examples/foerderband")
            session.add(hall)
            session.flush()
            machine = Machine(
                hall_id=hall.id,
                name=SOURCE_NAME,
                machine_type="conveyor",
                source_id=source.id,
                description="Werkstuecktransport Einlauf -> Auslauf, Wendeschuetz -K1/-K2, SPS -A1",
            )
            session.add(machine)
            session.flush()
            session.add_all(FaultEntry(machine_id=machine.id, **fault) for fault in FAULTS)
    finally:
        reset_workspace(token)
    for document_id in document_ids:
        ingest_document(document_id)
    logger.info("DEMO_MODE: Beispiel-Maschine %s angelegt", SOURCE_NAME)
    return True


def seed_in_background() -> threading.Thread:
    def run() -> None:
        try:
            seed_example()
        except Exception:  # noqa: BLE001 - die Demo startet auch ohne Beispiel
            # Traceback bleibt: eingelesen wird nur das oeffentliche Beispiel (examples/foerderband), kein Kundentext (SIN-130)
            logger.exception("DEMO_MODE: Beispiel-Maschine konnte nicht angelegt werden")

    thread = threading.Thread(target=run, name="demo-seed", daemon=True)
    thread.start()
    return thread
