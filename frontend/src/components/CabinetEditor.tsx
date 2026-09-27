"use client";

import { useEffect, useRef, useState } from "react";

import { plant, type Cabinet, type Hotspot, type TagLookup } from "@/lib/api";
import { matchesAny } from "@/lib/faults";
import type { PageTarget } from "@/components/PageViewer";

type Rect = { x: number; y: number; w: number; h: number };

const KINDS = ["Schütz", "Motorschutzschalter", "LS-Schalter", "Sicherung", "Netzteil", "SPS", "Relais", "Sicherheitsrelais", "Frequenzumrichter", "Klemmleiste", "Hauptschalter", "Sonstiges"];

/**
 * Bild eines Schaltschranks mit Hotspots. Rechteck aufziehen legt einen neuen Hotspot an,
 * Klick auf einen Hotspot zeigt die Fundstellen des BMK in der Doku der Maschine.
 * Vision-Vorschlaege (gestrichelt) werden bestaetigt oder verworfen.
 */
export function CabinetEditor({
  cabinet,
  machineId,
  highlightTag,
  highlightTags,
  onChanged,
  onOpenPage,
}: {
  cabinet: Cabinet;
  machineId: string;
  highlightTag?: string | null;
  /** Kennzeichen eines gewaehlten Fehlers: Bauteile rot markieren */
  highlightTags?: string[];
  onChanged: () => void;
  onOpenPage: (target: PageTarget) => void;
}) {
  const [draft, setDraft] = useState<Rect | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [lookup, setLookup] = useState<TagLookup | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const imageRef = useRef<HTMLDivElement>(null);
  const start = useRef<{ x: number; y: number } | null>(null);

  // Hervorhebung von aussen (Fehlerliste, Chat): beim Wechsel des Tags den Hotspot aktivieren.
  const [seenHighlight, setSeenHighlight] = useState<string | null | undefined>(undefined);
  if (highlightTag !== seenHighlight) {
    setSeenHighlight(highlightTag);
    const hit = highlightTag ? cabinet.hotspots.find((h) => h.tag.toUpperCase() === highlightTag.toUpperCase()) : null;
    if (hit) setActiveId(hit.id);
  }

  const active = cabinet.hotspots.find((h) => h.id === activeId) ?? null;

  useEffect(() => {
    if (!active?.tag) return;
    let cancelled = false;
    plant
      .lookupTag(machineId, active.tag)
      .then((result) => !cancelled && setLookup(result))
      .catch(() => !cancelled && setLookup(null));
    return () => {
      cancelled = true;
    };
  }, [active?.tag, machineId]);

  function relative(event: React.PointerEvent): { x: number; y: number } | null {
    const rect = imageRef.current?.getBoundingClientRect();
    if (!rect) return null;
    return {
      x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
    };
  }

  function onPointerDown(event: React.PointerEvent) {
    if (event.target !== imageRef.current && (event.target as HTMLElement).tagName !== "IMG") return;
    const p = relative(event);
    if (!p) return;
    start.current = p;
    setDraft({ x: p.x, y: p.y, w: 0, h: 0 });
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: React.PointerEvent) {
    const s = start.current;
    const p = relative(event);
    if (!s || !p) return;
    setDraft({ x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) });
  }

  async function onPointerUp() {
    const rect = draft;
    start.current = null;
    setDraft(null);
    if (!rect || rect.w < 0.01 || rect.h < 0.01) return;
    const tag = prompt("Betriebsmittelkennzeichen für dieses Bauteil (z. B. -K1), leer = später:") ?? "";
    try {
      const created = await plant.createHotspot(cabinet.id, { ...rect, tag: tag.trim(), label: "", kind: "", confirmed: true });
      onChanged();
      setActiveId(created.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function detect() {
    setBusy("Vision analysiert das Bild …");
    setError(null);
    try {
      await plant.detectCabinet(cabinet.id);
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function patch(hotspot: Hotspot, body: Parameters<typeof plant.updateHotspot>[1]) {
    await plant.updateHotspot(hotspot.id, body).catch((err) => setError(err.message));
    onChanged();
  }

  async function remove(hotspot: Hotspot) {
    await plant.deleteHotspot(hotspot.id).catch((err) => setError(err.message));
    if (activeId === hotspot.id) setActiveId(null);
    onChanged();
  }

  async function confirmAll() {
    const open = cabinet.hotspots.filter((h) => !h.confirmed);
    await Promise.all(open.map((h) => plant.updateHotspot(h.id, { confirmed: true }))).catch((err) => setError(err.message));
    onChanged();
  }

  const proposals = cabinet.hotspots.filter((h) => !h.confirmed).length;
  const shownLookup = active?.tag && lookup?.tag === active.tag ? lookup : null;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
          <button
            onClick={detect}
            disabled={!!busy}
            className="rounded-md border border-border px-2.5 py-1 hover:bg-secondary disabled:opacity-50"
            title="Claude Vision schlägt Bauteile und BMK vor (kostet API-Tokens)"
          >
            Bauteile erkennen lassen
          </button>
          {proposals > 0 && (
            <button onClick={confirmAll} className="rounded-md border border-primary bg-primary/10 px-2.5 py-1">
              {proposals} Vorschläge alle übernehmen
            </button>
          )}
          <span className="text-muted-foreground">Rechteck aufziehen = Bauteil markieren. Klick = Fundstellen in der Doku.</span>
          {busy && <span className="text-primary">{busy}</span>}
          {error && <span className="text-danger">{error}</span>}
        </div>

        <div
          ref={imageRef}
          className="relative w-full cursor-crosshair select-none overflow-hidden rounded-xl border border-border bg-secondary"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={plant.cabinetImageUrl(cabinet.id)} alt={cabinet.title} className="block w-full" draggable={false} />
          {cabinet.hotspots.map((hotspot) => {
            const isActive = hotspot.id === activeId;
            const isFault = Boolean(highlightTags?.length && matchesAny(hotspot.tag, highlightTags));
            return (
              <button
                key={hotspot.id}
                onPointerDown={(event) => event.stopPropagation()}
                onClick={() => setActiveId(isActive ? null : hotspot.id)}
                title={`${hotspot.tag || "(ohne BMK)"} ${hotspot.kind}`.trim()}
                className={`absolute rounded-sm border-2 text-[11px] font-semibold leading-none ${
                  isFault
                    ? "border-danger bg-danger/20 shadow-[0_0_0_4px_rgba(215,38,61,0.3)]"
                    : isActive
                    ? "border-primary bg-primary/25 text-primary-foreground"
                    : hotspot.confirmed
                      ? "border-primary/80 bg-primary/10 hover:bg-primary/25"
                      : "border-dashed border-ok/90 bg-ok/10 hover:bg-ok/25"
                }`}
                style={{ left: `${hotspot.x * 100}%`, top: `${hotspot.y * 100}%`, width: `${hotspot.w * 100}%`, height: `${hotspot.h * 100}%` }}
              >
                <span className={`absolute -top-0.5 left-0 -translate-y-full rounded-t px-1 py-0.5 text-primary-foreground ${isFault ? "bg-danger" : "bg-primary"}`}>
                  {hotspot.tag || "?"}
                </span>
              </button>
            );
          })}
          {draft && (
            <div
              className="pointer-events-none absolute border-2 border-dashed border-primary bg-primary/10"
              style={{ left: `${draft.x * 100}%`, top: `${draft.y * 100}%`, width: `${draft.w * 100}%`, height: `${draft.h * 100}%` }}
            />
          )}
        </div>
      </div>

      <aside className="space-y-3 text-sm">
        {!active ? (
          <div className="rounded-xl border border-border bg-card p-3 text-muted-foreground">
            <p className="font-medium text-foreground">{cabinet.hotspots.length} Bauteile markiert</p>
            <ul className="mt-2 max-h-72 space-y-1 overflow-y-auto">
              {cabinet.hotspots.map((h) => (
                <li key={h.id}>
                  <button onClick={() => setActiveId(h.id)} className="flex w-full gap-2 rounded px-1 text-left hover:bg-secondary">
                    <span className={`font-mono ${h.confirmed ? "text-foreground" : "text-ok"}`}>{h.tag || "?"}</span>
                    <span className="truncate">{h.kind || h.label}</span>
                    {!h.confirmed && <span className="ml-auto text-xs">Vorschlag</span>}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-card p-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-base font-semibold">{active.tag || "ohne BMK"}</span>
              {!active.confirmed && (
                <span className="rounded bg-ok/15 px-1.5 py-0.5 text-xs text-ok">
                  Vision {active.confidence != null ? `${Math.round(active.confidence * 100)} %` : ""}
                </span>
              )}
            </div>
            <label className="mt-2 block">
              <span className="text-xs text-muted-foreground">BMK</span>
              <input
                key={active.id + active.tag}
                defaultValue={active.tag}
                placeholder="-K1"
                onBlur={(event) => event.target.value.trim() !== active.tag && patch(active, { tag: event.target.value.trim() })}
                className="mt-0.5 w-full rounded-md border border-border bg-background px-2 py-1 font-mono"
              />
            </label>
            <label className="mt-2 block">
              <span className="text-xs text-muted-foreground">Bauteilart</span>
              <input
                key={active.id + active.kind}
                list="cabinet-kinds"
                defaultValue={active.kind}
                onBlur={(event) => event.target.value !== active.kind && patch(active, { kind: event.target.value })}
                className="mt-0.5 w-full rounded-md border border-border bg-background px-2 py-1"
              />
              <datalist id="cabinet-kinds">
                {KINDS.map((kind) => (
                  <option key={kind} value={kind} />
                ))}
              </datalist>
            </label>
            <label className="mt-2 block">
              <span className="text-xs text-muted-foreground">Beschreibung</span>
              <input
                key={active.id + active.label}
                defaultValue={active.label}
                onBlur={(event) => event.target.value !== active.label && patch(active, { label: event.target.value })}
                className="mt-0.5 w-full rounded-md border border-border bg-background px-2 py-1"
              />
            </label>
            <div className="mt-3 flex gap-2">
              {!active.confirmed && (
                <button onClick={() => patch(active, { confirmed: true })} className="rounded-md bg-primary px-2.5 py-1 text-primary-foreground">
                  Übernehmen
                </button>
              )}
              <button onClick={() => remove(active)} className="rounded-md border border-border px-2.5 py-1 hover:text-danger">
                Entfernen
              </button>
              <button onClick={() => setActiveId(null)} className="ml-auto text-muted-foreground hover:text-foreground">
                Schließen
              </button>
            </div>

            {active.tag && (
              <div className="mt-4 border-t border-border pt-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">In der Doku</h3>
                {shownLookup?.bom_line && <p className="mt-1 text-xs text-muted-foreground">Stückliste: …{shownLookup.bom_line}…</p>}
                {shownLookup && shownLookup.hits.length === 0 && (
                  <p className="mt-1 text-muted-foreground">Kein Treffer für {shownLookup.tag}. Ist eine Wissensquelle zugeordnet und fertig verarbeitet?</p>
                )}
                {!shownLookup && <p className="mt-1 text-muted-foreground">Suche Fundstellen …</p>}
                <ul className="mt-1 max-h-64 space-y-1 overflow-y-auto">
                  {shownLookup?.hits.map((hit, index) => (
                    <li key={index}>
                      <button
                        disabled={!hit.page}
                        onClick={() => hit.page && onOpenPage({ documentId: hit.document_id, filename: hit.filename, page: hit.page })}
                        className="w-full rounded px-1 text-left hover:bg-secondary disabled:cursor-default"
                      >
                        <span className="font-medium">{hit.filename}</span>
                        <span className="text-muted-foreground"> · {hit.page ? `S. ${hit.page}` : hit.section || hit.doc_type}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
