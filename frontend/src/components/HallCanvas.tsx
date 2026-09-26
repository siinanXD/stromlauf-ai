"use client";

import Link from "next/link";
import { useRef, useState } from "react";

import { MACHINE_TYPE_LABELS, type Flow, type Machine, type MachineType } from "@/lib/api";

const TILE_W = 168;
const TILE_H = 92;
const GRID = 24;

const TYPE_ICON: Record<MachineType, string> = {
  conveyor: "⟶",
  main: "⚙",
  packaging: "▣",
  robot: "🦾",
  storage: "▤",
  other: "◻",
};

function snap(value: number) {
  return Math.max(0, Math.round(value / GRID) * GRID);
}

/** Schnittpunkt der Linie Kachelmitte -> Ziel mit dem Kachelrand, damit die Pfeilspitze sichtbar bleibt. */
function edgePoint(cx: number, cy: number, tx: number, ty: number) {
  const dx = tx - cx;
  const dy = ty - cy;
  if (dx === 0 && dy === 0) return { x: cx, y: cy };
  const scale = Math.min((TILE_W / 2 + 6) / Math.abs(dx || 1e-6), (TILE_H / 2 + 6) / Math.abs(dy || 1e-6));
  return { x: cx + dx * scale, y: cy + dy * scale };
}

/**
 * Baukasten der Halle: Maschinen als Kacheln, per Maus verschiebbar, Materialfluss als Pfeile.
 * Positionen werden nach dem Loslassen gespeichert; im Fluss-Modus verbindet ein Klick auf zwei
 * Kacheln sie mit einem Pfeil.
 */
export function HallCanvas({
  machines,
  flows,
  onMoved,
  onFlowsChanged,
  selectedId,
  onSelect,
}: {
  machines: Machine[];
  flows: Flow[];
  onMoved: (id: string, x: number, y: number) => void;
  onFlowsChanged: (flows: Flow[]) => void;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  // Nur waehrend/nach dem Ziehen abweichende Positionen; sonst gilt die gespeicherte Position.
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});
  const [flowMode, setFlowMode] = useState(false);
  const [flowStart, setFlowStart] = useState<string | null>(null);
  const drag = useRef<{ id: string; dx: number; dy: number; moved: boolean } | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  function pos(id: string) {
    const machine = machines.find((m) => m.id === id);
    return positions[id] ?? { x: machine?.pos_x ?? 0, y: machine?.pos_y ?? 0 };
  }

  function onPointerDown(event: React.PointerEvent, machine: Machine) {
    if (flowMode) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const p = pos(machine.id);
    drag.current = { id: machine.id, dx: event.clientX - rect.left - p.x, dy: event.clientY - rect.top - p.y, moved: false };
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: React.PointerEvent) {
    const current = drag.current;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!current || !rect) return;
    current.moved = true;
    const x = snap(event.clientX - rect.left - current.dx);
    const y = snap(event.clientY - rect.top - current.dy);
    setPositions((all) => ({ ...all, [current.id]: { x, y } }));
  }

  function onPointerUp() {
    const current = drag.current;
    drag.current = null;
    if (!current) return;
    if (current.moved) {
      const p = pos(current.id);
      onMoved(current.id, p.x, p.y);
    }
  }

  function onTileClick(machine: Machine) {
    if (!flowMode) {
      onSelect(machine.id);
      return;
    }
    if (!flowStart) {
      setFlowStart(machine.id);
      return;
    }
    if (flowStart !== machine.id && !flows.some((f) => f.from_machine_id === flowStart && f.to_machine_id === machine.id)) {
      onFlowsChanged([...flows, { from_machine_id: flowStart, to_machine_id: machine.id, label: "" }]);
    }
    setFlowStart(null);
  }

  function removeFlow(flow: Flow) {
    onFlowsChanged(flows.filter((f) => !(f.from_machine_id === flow.from_machine_id && f.to_machine_id === flow.to_machine_id)));
  }

  const width = Math.max(900, ...machines.map((m) => pos(m.id).x + TILE_W + 80));
  const height = Math.max(520, ...machines.map((m) => pos(m.id).y + TILE_H + 80));

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2 text-sm">
        <button
          onClick={() => {
            setFlowMode(!flowMode);
            setFlowStart(null);
          }}
          className={`rounded-md border px-2.5 py-1 ${flowMode ? "border-primary bg-primary/10" : "border-border hover:bg-secondary"}`}
        >
          {flowMode ? "Fluss-Modus an: zwei Kacheln anklicken" : "Materialfluss zeichnen"}
        </button>
        <span className="text-muted-foreground">Kacheln ziehen zum Anordnen. Klick öffnet die Maschine rechts.</span>
      </div>

      <div className="min-h-0 flex-1 overflow-auto bg-background">
        <div
          ref={canvasRef}
          className="relative"
          style={{
            width,
            height,
            backgroundImage: "radial-gradient(var(--border) 1px, transparent 1px)",
            backgroundSize: `${GRID}px ${GRID}px`,
          }}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onClick={(event) => {
            if (event.target === canvasRef.current) onSelect(null);
          }}
        >
          <svg className="pointer-events-none absolute inset-0" width={width} height={height}>
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--primary)" />
              </marker>
            </defs>
            {flows.map((flow) => {
              const a = pos(flow.from_machine_id);
              const b = pos(flow.to_machine_id);
              const ca = { x: a.x + TILE_W / 2, y: a.y + TILE_H / 2 };
              const cb = { x: b.x + TILE_W / 2, y: b.y + TILE_H / 2 };
              const { x: x1, y: y1 } = edgePoint(ca.x, ca.y, cb.x, cb.y);
              const { x: x2, y: y2 } = edgePoint(cb.x, cb.y, ca.x, ca.y);
              const mx = (x1 + x2) / 2;
              const my = (y1 + y2) / 2;
              return (
                <g key={`${flow.from_machine_id}-${flow.to_machine_id}`}>
                  <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--primary)" strokeWidth={2.5} markerEnd="url(#arrow)" />
                  <g className="pointer-events-auto cursor-pointer" onClick={() => removeFlow(flow)}>
                    <circle cx={mx} cy={my} r={9} fill="var(--card)" stroke="var(--border)" />
                    <text x={mx} y={my + 4} textAnchor="middle" fontSize="11" fill="var(--muted-foreground)">
                      ✕
                    </text>
                  </g>
                </g>
              );
            })}
          </svg>

          {machines.map((machine) => {
            const p = pos(machine.id);
            const selected = machine.id === selectedId || machine.id === flowStart;
            return (
              <div
                key={machine.id}
                role="button"
                tabIndex={0}
                onPointerDown={(event) => onPointerDown(event, machine)}
                onClick={() => onTileClick(machine)}
                className={`absolute select-none rounded-xl border bg-card p-2.5 shadow-sm ${
                  selected ? "border-primary ring-2 ring-primary/30" : "border-border hover:border-primary"
                } ${flowMode ? "cursor-crosshair" : "cursor-grab active:cursor-grabbing"}`}
                style={{ left: p.x, top: p.y, width: TILE_W, height: TILE_H }}
              >
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span>{TYPE_ICON[machine.machine_type] ?? "◻"}</span>
                  <span className="truncate">{MACHINE_TYPE_LABELS[machine.machine_type] ?? machine.machine_type}</span>
                </div>
                <div className="mt-1 truncate font-medium" title={machine.name}>
                  {machine.name}
                </div>
                <div className="mt-1.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                  <span title="Dokumente">📄 {machine.document_count}</span>
                  <span title="Fehlereinträge" className={machine.fault_count ? "text-danger" : ""}>
                    ⚠ {machine.fault_count}
                  </span>
                  <span title="Schaltschrankbilder">▦ {machine.cabinet_count}</span>
                  <Link
                    href={`/werk/maschine/${machine.id}`}
                    onClick={(event) => event.stopPropagation()}
                    onPointerDown={(event) => event.stopPropagation()}
                    className="ml-auto rounded px-1 text-primary hover:bg-primary/10"
                  >
                    öffnen
                  </Link>
                </div>
              </div>
            );
          })}

          {machines.length === 0 && (
            <p className="absolute left-6 top-6 max-w-md text-sm text-muted-foreground">
              Noch keine Maschinen. Rechts eine anlegen, dann hier anordnen und den Materialfluss zeichnen.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
