"""Vergleich Extraktion gegen Gold-JSON: Recall/Precision der I/O-Liste, Schrittanzahl, Belegqualitaet.

Beide Seiten sind MachineFlow-Instanzen. I/O-Punkte werden ueber die normalisierte Adresse gepaart;
je Treffer zaehlen zusaetzlich Symbol, Richtung, Art (kind) und Kontaktart, sofern das Gold sie nennt.
"""

from collections import Counter

from app.flow.schema import MachineFlow
from app.ingestion.tags import normalize_tag


def _ratio(hits: int, total: int) -> float | None:
    return round(hits / total, 3) if total else None


def compare(gold: MachineFlow, pred: MachineFlow) -> dict:
    gold_io = {normalize_tag(p.address): p for p in gold.io_points}
    pred_io = {normalize_tag(p.address): p for p in pred.io_points}
    matched = sorted(set(gold_io) & set(pred_io))
    missing = sorted(set(gold_io) - set(pred_io))
    extra = sorted(set(pred_io) - set(gold_io))

    field_hits: Counter = Counter()
    field_totals: Counter = Counter()
    for address in matched:
        g, p = gold_io[address], pred_io[address]
        for name, g_value, p_value in (
            ("symbol", g.symbol, p.symbol),
            ("direction", g.direction, p.direction),
            ("kind", g.kind, p.kind),
            ("contact", g.contact, p.contact),
            ("tag", normalize_tag(g.tag) if g.tag else "", normalize_tag(p.tag) if p.tag else ""),
        ):
            if g_value in ("", None):
                continue  # Gold sagt nichts: nicht bewerten
            field_totals[name] += 1
            if str(g_value).lower() == str(p_value or "").lower():
                field_hits[name] += 1

    gold_steps, pred_steps = len(gold.steps), len(pred.steps)
    gold_transitions = sum(len(s.transitions) for s in gold.steps)
    pred_transitions = sum(len(s.transitions) for s in pred.steps)
    gold_names = {s.name.strip().lower() for s in gold.steps}
    pred_names = {s.name.strip().lower() for s in pred.steps}

    evidence = [p for p in pred.io_points] + [s for s in pred.steps] + [t for s in pred.steps for t in s.transitions]
    assumptions = sum(1 for e in evidence if e.assumption)
    confidence = round(sum(e.confidence for e in evidence) / len(evidence), 3) if evidence else None

    return {
        "io": {
            "gold": len(gold_io),
            "pred": len(pred_io),
            "matched": len(matched),
            "recall": _ratio(len(matched), len(gold_io)),
            "precision": _ratio(len(matched), len(pred_io)),
            "missing": missing,
            "extra": extra,
            "fields": {name: _ratio(field_hits[name], field_totals[name]) for name in sorted(field_totals)},
        },
        "steps": {
            "gold": gold_steps,
            "pred": pred_steps,
            "delta": pred_steps - gold_steps,
            "count_ok": abs(pred_steps - gold_steps) <= max(1, round(gold_steps * 0.25)),
            "names_recall": _ratio(len(gold_names & pred_names), len(gold_names)),
            "transitions_gold": gold_transitions,
            "transitions_pred": pred_transitions,
        },
        "evidence": {
            "objects": len(evidence),
            "assumptions": assumptions,
            "assumption_share": _ratio(assumptions, len(evidence)),
            "mean_confidence": confidence,
            "unresolved_refs": pred.unresolved_refs(),
        },
        "meta": {
            "cached": pred.meta.cached,
            "cost_usd": pred.meta.total.cost_usd,
            "latency_ms": pred.meta.total.latency_ms,
            "trace_id": pred.meta.trace_id,
            "prompt_version": pred.meta.prompt_version,
            "models": pred.meta.models,
        },
    }


def is_template(flow: MachineFlow) -> bool:
    """Gold-Vorlage noch nicht ausgefuellt (Markierung VORLAGE in summary)."""
    return flow.summary.strip().upper().startswith("VORLAGE")
