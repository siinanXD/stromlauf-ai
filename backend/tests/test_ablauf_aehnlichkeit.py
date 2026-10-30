import math

import pytest

from app.ablauf.aehnlichkeit import ABSTAND, mittelwert_vektor, ordne_zu


def test_mittelwert_ist_normiert():
    vektor = mittelwert_vektor([[1.0, 0.0], [0.0, 1.0]])
    assert vektor == pytest.approx([math.sqrt(0.5), math.sqrt(0.5)])
    assert math.hypot(*vektor) == pytest.approx(1.0)


def test_mittelwert_eines_vektors_ist_dessen_richtung():
    assert mittelwert_vektor([[3.0, 4.0]]) == pytest.approx([0.6, 0.8])


def test_mittelwert_leere_liste_wirft():
    with pytest.raises(ValueError):
        mittelwert_vektor([])


def test_mittelwert_verschiedene_laengen_wirft():
    with pytest.raises(ValueError):
        mittelwert_vektor([[1.0, 0.0], [1.0]])


def test_mittelwert_heben_sich_auf_wirft():
    # Nullvektor als Mittel hat keine Richtung; eine Gruppe daraus wuerde nan liefern.
    with pytest.raises(ValueError):
        mittelwert_vektor([[1.0, 0.0], [-1.0, 0.0]])


def test_treffer_liefert_gruppe_und_wert():
    gruppen = {"FB01": [1.0, 0.0], "UR01": [0.0, 1.0]}
    gruppe, wert = ordne_zu([0.9, 0.1], gruppen, schwelle=0.5)
    assert gruppe == "FB01"
    assert wert == pytest.approx(0.9 / math.hypot(0.9, 0.1))


def test_knapp_unter_der_schwelle_bleibt_unzugeordnet():
    gruppen = {"FB01": [1.0, 0.0]}
    _, wert = ordne_zu([0.8, 0.6], gruppen, schwelle=0.0)
    gruppe, bester = ordne_zu([0.8, 0.6], gruppen, schwelle=wert + 1e-9)
    assert gruppe is None
    assert bester == wert


def test_genau_auf_der_schwelle_ist_zugeordnet():
    gruppen = {"FB01": [1.0, 0.0]}
    _, wert = ordne_zu([0.8, 0.6], gruppen, schwelle=0.0)
    assert ordne_zu([0.8, 0.6], gruppen, schwelle=wert) == ("FB01", wert)


def test_gleichstand_ist_nie_eine_stille_wahl():
    gruppen = {"FB01": [1.0, 0.0], "UR01": [0.0, 1.0]}
    gruppe, wert = ordne_zu([1.0, 1.0], gruppen, schwelle=0.5)
    assert gruppe is None
    assert wert == pytest.approx(math.sqrt(0.5))


def _winkel(grad: float) -> list[float]:
    return [math.cos(math.radians(grad)), math.sin(math.radians(grad))]


def test_kleiner_abstand_der_besten_zwei_bleibt_unzugeordnet():
    gruppen = {"A": [1.0, 0.0], "B": [0.0, 1.0]}
    # cos 44 - cos 46 = 0,025, unter ABSTAND
    assert ordne_zu(_winkel(44.0), gruppen, schwelle=0.0)[0] is None


def test_klarer_abstand_ordnet_zu():
    gruppen = {"A": [1.0, 0.0], "B": [0.0, 1.0]}
    assert ordne_zu(_winkel(30.0), gruppen, schwelle=0.0)[0] == "A"


def test_abstand_an_der_grenze():
    gruppen = {"A": [1.0, 0.0], "B": [0.0, 1.0]}
    datei = _winkel(40.0)
    abstand = math.cos(math.radians(40.0)) - math.sin(math.radians(40.0))
    # Gleitkomma: beidseitig mit Toleranz pruefen statt auf das letzte Bit.
    assert ordne_zu(datei, gruppen, schwelle=0.0, abstand=abstand - 1e-9)[0] == "A"
    assert ordne_zu(datei, gruppen, schwelle=0.0, abstand=abstand + 1e-9)[0] is None


def test_standardabstand():
    assert ABSTAND == 0.03


def test_ohne_gruppen_bleibt_unzugeordnet():
    assert ordne_zu([1.0, 0.0], {}, schwelle=0.5) == (None, 0.0)


def test_nullvektor_wirft():
    with pytest.raises(ValueError):
        ordne_zu([0.0, 0.0], {"A": [1.0, 0.0]}, schwelle=0.5)
    with pytest.raises(ValueError):
        ordne_zu([1.0, 0.0], {"A": [0.0, 0.0]}, schwelle=0.5)


def test_verschiedene_laengen_werfen():
    with pytest.raises(ValueError):
        ordne_zu([1.0, 0.0, 0.0], {"A": [1.0, 0.0]}, schwelle=0.5)


@pytest.mark.parametrize("schlecht", [math.nan, math.inf])
def test_nicht_endliche_werte_werfen(schlecht):
    with pytest.raises(ValueError):
        ordne_zu([schlecht, 1.0], {"A": [1.0, 0.0]}, schwelle=0.5)


def test_einstellungen_haben_standardwerte():
    from app.config import Settings

    einstellungen = Settings(_env_file=None)
    assert einstellungen.ablauf_aehnlichkeit_abstand == ABSTAND
    assert 0.0 < einstellungen.ablauf_aehnlichkeit_schwelle < 1.0
