"""Modul-Fixtures mit eigener Umgebung geben sie beim Abbau zurueck (Review zu SIN-1216/SIN-1220).

Sonst sehen spaetere Tests im selben Lauf das JWT-Secret und DATA_DIR eines anderen Moduls: offene Anfragen
verlangen ploetzlich Anmeldung, Tokens mit dem eigentlichen Secret fallen durch.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)


@pytest.mark.parametrize("module", ["tests.test_map_overrides_api", "tests.test_cabinet_location_api"])
def test_client_fixture_stellt_umgebung_wieder_her(module, tmp_path_factory, monkeypatch):
    import importlib

    from app.config import get_settings

    monkeypatch.setenv("JWT_SECRET", "vorher-test-secret-0123456789")
    monkeypatch.setenv("DATA_DIR", str(tmp_path_factory.mktemp("vorher")))
    before = {key: os.environ[key] for key in ("JWT_SECRET", "DATA_DIR")}

    fixture = importlib.import_module(module).client.__wrapped__(tmp_path_factory)
    next(fixture)
    for _ in fixture:  # Abbau
        pass

    assert {key: os.environ.get(key) for key in before} == before
    get_settings.cache_clear()
