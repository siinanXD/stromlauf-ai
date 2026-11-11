"""Vertrauensmass je Seite (SIN-1226): reine Funktion und Messung an den Beispielplaenen, ohne Datenbank und Modell."""

from pathlib import Path

import pytest

from app.config import Settings
from app.ingestion.page_confidence import THRESHOLD, PageReading, confidence, read_pages

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
PLANS = (
    "foerderband/01_Stromlaufplan_FB-01.pdf",
    "umroller/01_Stromlaufplan_UR-01.pdf",
    "aufrollung/01_Stromlaufplan_PM1-AR.pdf",
)
FULL = PageReading(sheet_read=True, header=True, tags=20, words=150, ends=24, named_ends=24)


def test_seite_mit_allem_gelesen_liegt_ueber_der_schwelle():
    assert confidence(FULL) == 1.0
    assert confidence(FULL) >= THRESHOLD


def test_leere_seite_liegt_darunter():
    assert confidence(PageReading()) < THRESHOLD


def test_scan_ohne_blattnummer_liegt_darunter():
    # Text per OCR vorhanden, aber weder Schriftfeld noch Kopfzeile erkannt
    scan = PageReading(sheet_read=False, header=False, tags=20, words=150)
    assert confidence(scan) < THRESHOLD


def test_seite_ohne_benannte_netzenden_liegt_darunter():
    unnamed = PageReading(sheet_read=True, header=True, tags=20, words=150, ends=24, named_ends=0)
    assert confidence(unnamed) < THRESHOLD


def test_wenige_kennzeichen_im_text_senken_das_mass():
    prose = PageReading(sheet_read=True, header=True, tags=1, words=400)
    assert confidence(prose) < confidence(FULL)
    assert confidence(prose) < THRESHOLD


def test_einstellungen_stehen_in_settings_und_folgen_der_konstante():
    fields = Settings.model_fields
    assert fields["page_reader_fallback"].default is True
    assert fields["page_reader_threshold"].default == THRESHOLD


@pytest.mark.parametrize("plan", PLANS)
def test_jede_seite_der_beispielanlagen_liegt_ueber_der_schwelle(plan):
    pages = read_pages(EXAMPLES / plan)
    assert pages
    below = {page: round(confidence(r), 2) for page, r in pages.items() if confidence(r) < THRESHOLD}
    assert not below


def test_voll_scan_liegt_auf_jeder_seite_unter_der_schwelle():
    pages = read_pages(EXAMPLES / "scan" / "01_Stromlaufplan_FB-01_scan.pdf")
    assert len(pages) == 7
    assert all(confidence(r) < THRESHOLD for r in pages.values())
