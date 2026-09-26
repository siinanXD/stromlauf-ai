"""Stueckliste (xlsx), Klemmenplan (csv), AWL, Symboltabelle (sdf), Betriebsanleitung (md) aus dem Modell."""

import csv
from pathlib import Path

from model import Machine, Refs
from openpyxl import Workbook
from openpyxl.styles import Font


def terminal_rows(m: Machine, refs: Refs, probe: bool = False) -> list[tuple[str, str, str, str, str]]:
    """Klemmenplan-Zeilen (Klemme, intern, extern, Funktion, Blatt). probe=True: ohne Verweise."""
    ref = (lambda bmk: "") if probe else (lambda bmk: refs.get(bmk) if refs.has(bmk) else "")
    x1, x2 = m.supply_strips
    rows: list[tuple[str, str, str, str, str]] = []
    for signal in m.inputs:
        card = f"-A1.{1 + m.inputs.index(signal) // 16}"
        rows.append((signal.terminal, f"{card}:{1 + m.inputs.index(signal) % 16} ({signal.address})",
                     f"{signal.device}:{signal.pins[1]}" + (" (BK)" if signal.kind == "sensor" else ""), signal.comment[:40], ref(signal.terminal)))
    sensors = ", ".join(f"{s.device}:1 (BN)" for s in m.sensors) or "-"
    sensors0 = ", ".join(f"{s.device}:3 (BU)" for s in m.sensors) or "-"
    a, b = m.sensor_supply
    rows.append((a, f"{x2}:1 (+24V)", sensors, "+24 V Sensoren", ref(a)))
    rows.append((b, f"{x2}:2 (0V)", sensors0, "0 V Sensoren", ref(b)))
    do_card_base = 1 + (len(m.inputs) - 1) // 16
    for i, signal in enumerate(m.outputs):
        card = f"-A1.{do_card_base + 1 + i // 16}"
        pin = f"{signal.device}:{signal.pins[0]}"
        rows.append((signal.terminal, f"{card}:{1 + i % 16} ({signal.address})", pin, signal.comment[:40], ref(signal.terminal)))
    coils = ", ".join(f"{s.device}:A2" for s in m.outputs if s.kind == "coil") or "-"
    lamps = ", ".join(f"{s.device}:X2" for s in m.outputs if s.kind in {"lamp", "horn"}) or "-"
    rows.append((m.coil_return, f"{x2}:2 (0V)", coils, "0 V Schuetzspulen", ref(m.coil_return)))
    rows.append((m.lamp_return, f"{x2}:2 (0V)", lamps, "0 V Meldeleuchten und Hupe", ref(m.lamp_return)))
    for drive in m.drives:
        for phase in ("U", "V", "W"):
            t = f"{drive.strip}:{phase}"
            rows.append((t, f"{drive.switch}:{phase}", f"{drive.motor}:{phase}1", f"Motor {drive.name} Phase {phase}", ref(t)))
        t = f"{drive.strip}:PE"
        rows.append((t, "PE-Schiene", f"{drive.motor}:PE", "Schutzleiter", ref(t)))
    rows += [
        (f"{x1}:1", "-Q1:1", "Netz L1", "Einspeisung L1", ref(f"{x1}:1")),
        (f"{x1}:2", "-Q1:3", "Netz L2", "Einspeisung L2", ref(f"{x1}:2")),
        (f"{x1}:3", "-Q1:5", "Netz L3", "Einspeisung L3", ref(f"{x1}:3")),
        (f"{x1}:N", "-T1:N", "Netz N", "Neutralleiter", ref(f"{x1}:N")),
        (f"{x1}:PE", "PE-Schiene", "Netz PE", "Schutzleiter", ref(f"{x1}:PE")),
        (f"{x2}:1", "-T1:+", f"{a}", "+24 V Sensoren", ref(f"{x2}:1")),
        (f"{x2}:2", "-T1:-", f"{b}, {m.coil_return}, {m.lamp_return}", "0 V", ref(f"{x2}:2")),
        (f"{x2}:3", "-T1:+", ", ".join(f"{c.relay}:A1" for c in m.safety), "+24 V Sicherheitskreise", ref(f"{x2}:3")),
        (f"{x2}:4", "-T1:-", ", ".join(f"{c.relay}:A2" for c in m.safety), "0 V Sicherheitskreise", ref(f"{x2}:4")),
        (f"{x2}:5", "-T1:+", "-A1:L+, " + ", ".join(f"{d.switch}:24V" for d in m.drives if d.kind == "vfd"), "+24 V SPS und Umrichter", ref(f"{x2}:5")),
        (f"{x2}:6", "-T1:-", "-A1:M", "0 V SPS und Umrichter", ref(f"{x2}:6")),
    ]
    for circuit in m.safety:
        rows.append((circuit.release_terminal, f"{circuit.relay}:14", circuit.release_text[:40], "+24 V freigegeben", ref(circuit.release_terminal)))
        chain = ", ".join(bmk for bmk, _, _ in circuit.devices)
        for channel in (1, 2):
            first, last = circuit.devices[0], circuit.devices[-1]
            pins_first = first[channel].split("/")
            pins_last = last[channel].split("/")
            start = m.safety_terminals[(circuit.relay, channel, "start")]
            end = m.safety_terminals[(circuit.relay, channel, "end")]
            rows.append((start, f"{circuit.relay}:S{channel}1", f"{first[0]}:{pins_first[0]}", f"{circuit.name[:22]} Kanal {channel} Beginn", ref(start)))
            rows.append((end, f"{circuit.relay}:S{channel}2", f"{last[0]}:{pins_last[1]} (Reihe: {chain})", f"{circuit.name[:22]} Kanal {channel} Ende", ref(end)))
    return rows


def _file(m: Machine, n: int, kind: str, ext: str) -> str:
    return f"{n:02d}_{kind}_{m.code}.{ext}"


def stueckliste(m: Machine, refs: Refs, out: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Stueckliste"
    ws.append([f"Stueckliste {m.title}", "", "", "", "", ""])
    ws.append([f"Anlage {m.plant}, Schaltschrank {m.loc_cabinet}, Feld {m.loc_field}. Testdokumentation, frei erfunden, ohne Herstellerbezug.", "", "", "", "", ""])
    ws.append([])
    ws.append(["BMK", "Bezeichnung", "Typ / Kenndaten", "Menge", "Einbauort", "Blatt"])
    for cell in ws[4]:
        cell.font = Font(bold=True)
    for d in m.devices:
        ws.append([d.bmk, d.name, d.typ, d.qty, m.loc_field if d.in_field else m.loc_cabinet, refs.get(d.bmk) if refs.has(d.bmk) else ""])
    ws.append([])
    for bmk, name, spec, near in m.cables:
        ws.append([bmk, name, spec, 1, f"{m.loc_cabinet} -> {m.loc_field}", refs.get(near) if refs.has(near) else ""])
    for i, w in enumerate([10, 46, 44, 8, 16, 8]):
        ws.column_dimensions[chr(65 + i)].width = w
    wb.save(out / _file(m, 2, "Stueckliste", "xlsx"))


def klemmenplan(m: Machine, refs: Refs, out: Path) -> None:
    with (out / _file(m, 3, "Klemmenplan", "csv")).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Klemmleiste", "Klemme", "Ziel intern", "Ziel extern", "Funktion", "Blatt"])
        for row in terminal_rows(m, refs):
            w.writerow([row[0].split(":")[0], *row])


def _awl_addr(address: str) -> str:
    """E0.3 -> 'E      0.3' wie im STEP-7-Quelltext."""
    return f"{address[0]}{'':6}{address[1:]}"


def awl(m: Machine, out: Path) -> None:
    def var_block(name: str, signals) -> str:
        return f"{name}\n" + "".join(f"  {s.symbol} : BOOL ;\t//{s.comment} ({s.address})\n" for s in signals) + "END_VAR\n"

    statics = "VAR\n" + "".join(f"  {n} : {t} ;\t//{c}\n" for n, t, c in m.fb_static) + "END_VAR\n"
    call = "".join(f"       {s.symbol:<24} :={_awl_addr(s.address)}\n" for s in m.inputs + m.outputs)
    text = (
        f"FUNCTION_BLOCK FB {m.fb_number}\nTITLE ={m.fb_title}\n"
        f"//{m.title}: {m.function[0]}\n//Anlage {m.plant}, Schaltschrank {m.loc_cabinet}.\n"
        f"AUTHOR : Beispiel\nFAMILY : {m.code.replace('-', '')}\nNAME : {m.code.replace('-', '')[:8]}\nVERSION : 1.0\n\n"
        + var_block("VAR_INPUT", m.inputs) + var_block("VAR_OUTPUT", m.outputs) + statics
        + "BEGIN\n" + m.networks.strip("\n") + "\nEND_FUNCTION_BLOCK\n\n"
        f"DATA_BLOCK DB {m.db_number}\nTITLE =Instanz {m.title}\nVERSION : 1.0\n FB {m.fb_number}\nBEGIN\nEND_DATA_BLOCK\n\n"
        'ORGANIZATION_BLOCK OB 1\nTITLE = "Main Program Sweep (Cycle)"\nVERSION : 1.0\n\nVAR_TEMP\n'
        "  OB1_EV_CLASS : BYTE ;\n  OB1_SCAN_1 : BYTE ;\n  OB1_PRIORITY : BYTE ;\n  OB1_OB_NUMBR : BYTE ;\n"
        "  OB1_RESERVED_1 : BYTE ;\n  OB1_RESERVED_2 : BYTE ;\n  OB1_PREV_CYCLE : INT ;\n  OB1_MIN_CYCLE : INT ;\n"
        "  OB1_MAX_CYCLE : INT ;\n  OB1_DATE_TIME : DATE_AND_TIME ;\nEND_VAR\nBEGIN\nNETWORK\n"
        f"TITLE =Aufruf {m.title}\n//Eingaenge -A1.1 ff., Ausgaenge siehe DO-Blaetter\n"
        f"      CALL  FB    {m.fb_number} , DB    {m.db_number}\n{call}      NOP   0;\n"
        + m.ob_extra.strip("\n") + "\nEND_ORGANIZATION_BLOCK\n"
    )
    (out / _file(m, 4, "SPS_Programm", "awl")).write_text(text, encoding="utf-8", newline="\r\n")


def symbole(m: Machine, out: Path) -> None:
    def sdf_addr(address: str) -> str:
        for prefix in ("MW", "MB", "MD"):
            if address.startswith(prefix):
                return f"{prefix} {address[len(prefix):]}"
        return f"{address[0]} {address[1:]}"

    rows = [(s.symbol, sdf_addr(s.address), "BOOL", s.comment) for s in m.inputs + m.outputs]
    rows += [(sym, sdf_addr(addr), "INT" if addr.startswith("MW") else "BOOL", comment) for addr, sym, comment in m.merker]
    rows += list(m.extra_symbols)
    rows += [
        (f"FB_{m.code.replace('-', '')}", f"FB {m.fb_number}", f"FB {m.fb_number}", m.fb_title),
        (f"DB_{m.code.replace('-', '')}", f"DB {m.db_number}", f"FB {m.fb_number}", f"Instanz {m.title}"),
        ("Zyklus", "OB 1", "OB 1", "Main Program Sweep (Cycle)"),
    ]
    with (out / _file(m, 5, "Symboltabelle", "sdf")).open("w", newline="", encoding="latin-1", errors="replace") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        for r in rows:
            w.writerow(r)


def anleitung(m: Machine, refs: Refs, out: Path) -> None:
    man = m.manual
    fill = lambda text: m.fill(refs, text)  # noqa: E731 - kurze lokale Hilfe
    io_rows = "\n".join(f"| {s.address} | {s.symbol} | {s.comment} | {s.device} | {s.terminal} |" for s in m.inputs + m.outputs)
    controls = "\n".join(f"| {e} | {b} | {fill(f)} |" for e, b, f in man["bedienelemente"])
    steps = "\n".join(f"{i + 1}. {fill(step)}" for i, step in enumerate(man["einschalten"]))
    faults = "\n".join(f"| {fill(f.symptom)} | {fill(f.cause)} | {fill(f.check)} |" for f in m.faults)
    maintenance = "\n".join(f"- {fill(line)}" for line in man["wartung"])
    drives = "\n".join(
        f"| {d.motor} | {d.name} | {d.kw:g} kW, {d.amps:g} A, {d.rpm} 1/min | {d.switch} ({'Umrichter' if d.kind == 'vfd' else 'Schuetz'}) | {d.breaker} | {refs.get(d.motor)} |"
        for d in m.drives
    )
    text = f"""# Betriebsanleitung {m.title}

Anlage {m.plant}, Schaltschrank {m.loc_cabinet}, Feld {m.loc_field}. Testdokumentation fuer Stromlauf AI,
frei erfunden. Zugehoerige Dokumente: Stromlaufplan {m.drawing_no}, Stueckliste {m.code}, Klemmenplan {m.code},
SPS-Programm {m.code} (AWL, FB{m.fb_number}/DB{m.db_number}/OB1), Symboltabelle {m.code}.

## 1. Bestimmungsgemaesse Verwendung

{fill(man["verwendung"])}

## 2. Antriebe

| Motor | Funktion | Kenndaten | Ansteuerung | Schutz | Blatt |
| --- | --- | --- | --- | --- | --- |
{drives}

## 3. Bedienelemente am Bedienpult ({m.loc_field})

| Element | BMK | Funktion |
| --- | --- | --- |
{controls}

## 4. Einschalten

{steps}

## 5. Ausschalten und Not-Halt

{fill(man["ausschalten"])}

## 6. SPS-Belegung

| Adresse | Symbol | Bedeutung | Geraet | Klemme |
| --- | --- | --- | --- | --- |
{io_rows}

## 7. Stoerungen und Fehlersuche

| Symptom | Moegliche Ursache | Pruefung |
| --- | --- | --- |
{faults}

## 8. Wartung

{maintenance}
"""
    (out / _file(m, 6, "Betriebsanleitung", "md")).write_text(text, encoding="utf-8")


def render_all(m: Machine, refs: Refs, out: Path) -> None:
    stueckliste(m, refs, out)
    klemmenplan(m, refs, out)
    awl(m, out)
    symbole(m, out)
    anleitung(m, refs, out)
