"use client";

import { Check, Pencil, X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Dialog, DialogDescription, DialogOverlay, DialogPortal, DialogTitle } from "@/components/ui/dialog";
import { plant, type Cabinet, type Hotspot } from "@/lib/api";
import { clampBox, moveBy, nudge, resizeBy, sameBox, type Box, type Handle } from "@/lib/bbox";
import { matchesAny } from "@/lib/faults";
import { cn } from "@/lib/utils";

/**
 * Schaltschrankfoto als Lightbox (ux-spec §3.4): referenzierte Rahmen amber und gefuellt, andere als Umriss,
 * Seitenliste mit Konfidenz. "Markierung korrigieren" macht den gewaehlten Rahmen zieh- und skalierbar
 * (Ecken, Pfeiltasten, Shift+Pfeile skaliert), Enter speichert (PATCH -> origin manual), Esc bricht ab.
 */
export function CabinetLightbox({
  cabinet,
  hotspotId,
  referencedTags,
  onClose,
  onChanged,
}: {
  cabinet: Cabinet;
  hotspotId: string | null;
  referencedTags: string[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const [activeId, setActiveId] = useState<string | null>(hotspotId);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Box | null>(null);
  const [saving, setSaving] = useState(false);
  const imageRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; handle: Handle | "move" } | null>(null);

  const active = cabinet.hotspots.find((h) => h.id === activeId) ?? null;

  // Wechsel des gewaehlten Rahmens beendet eine laufende Korrektur (Zustand beim Rendern angleichen)
  const [editedId, setEditedId] = useState<string | null>(activeId);
  if (editedId !== activeId) {
    setEditedId(activeId);
    setEditing(false);
    setDraft(null);
  }

  function startEdit() {
    if (!active) return;
    setDraft(clampBox({ x: active.x, y: active.y, w: active.w, h: active.h }));
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false);
    setDraft(null);
  }

  async function save() {
    if (!active || !draft) return;
    if (sameBox(draft, { x: active.x, y: active.y, w: active.w, h: active.h })) return cancelEdit();
    setSaving(true);
    try {
      await plant.updateHotspot(active.id, draft);
      toast.success(`Rahmen von ${active.tag || "Bauteil"} gespeichert`);
      cancelEdit();
      onChanged();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  function size() {
    const rect = imageRef.current?.getBoundingClientRect();
    return { width: rect?.width ?? 0, height: rect?.height ?? 0 };
  }

  function onPointerDown(event: React.PointerEvent, handle: Handle | "move") {
    if (!editing) return;
    event.stopPropagation();
    drag.current = { x: event.clientX, y: event.clientY, handle };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: React.PointerEvent) {
    const d = drag.current;
    if (!d || !draft) return;
    const { width, height } = size();
    const dx = event.clientX - d.x;
    const dy = event.clientY - d.y;
    drag.current = { ...d, x: event.clientX, y: event.clientY };
    setDraft(d.handle === "move" ? moveBy(draft, dx, dy, width, height) : resizeBy(draft, d.handle, dx, dy, width, height));
  }

  function onPointerUp() {
    drag.current = null;
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (!editing || !draft) return;
    if (event.key === "Enter") {
      event.preventDefault();
      void save();
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      cancelEdit();
      return;
    }
    const next = nudge(draft, event.key, event.shiftKey);
    if (next) {
      event.preventDefault();
      setDraft(next);
    }
  }

  const styleOf = (b: Box) => ({ left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` });
  const isReferenced = (h: Hotspot) => matchesAny(h.tag, referencedTags);

  return (
    <Dialog open onOpenChange={(open) => !open && !editing && onClose()}>
      <DialogPortal>
        <DialogOverlay className="bg-black/70" />
        <DialogPrimitive.Content
          data-testid="cabinet-lightbox"
          className="fixed inset-0 z-50 flex flex-col bg-nav text-nav-foreground-strong outline-none md:inset-4 md:rounded-2xl md:border md:border-[#2a2f39]"
          onEscapeKeyDown={(e) => {
            if (editing) {
              e.preventDefault();
              cancelEdit();
            }
          }}
          onKeyDown={onKeyDown}
        >
          <header className="flex items-center gap-3 border-b border-[#2a2f39] px-4 py-2.5">
            <div className="min-w-0 flex-1">
              <DialogTitle className="truncate text-[15px] font-semibold">{cabinet.title}</DialogTitle>
              <DialogDescription className="text-xs text-nav-foreground">
                {cabinet.hotspots.length} Bauteile markiert · {referencedTags.length > 0 ? "amber = in der Antwort referenziert" : "Klick auf einen Rahmen zeigt das Bauteil"}
              </DialogDescription>
            </div>
            {active && !editing && (
              <button type="button" onClick={startEdit} className="inline-flex items-center gap-1.5 rounded-lg border border-[#3a4150] px-2.5 py-1.5 text-sm hover:bg-nav-hover" data-testid="edit-box">
                <Pencil className="size-4" /> Markierung korrigieren
              </button>
            )}
            {editing && (
              <>
                <span className="hidden text-xs text-nav-foreground sm:inline">Ziehen oder Pfeiltasten (Shift = Größe) · Enter speichert · Esc bricht ab</span>
                <button type="button" onClick={cancelEdit} className="rounded-lg border border-[#3a4150] px-2.5 py-1.5 text-sm hover:bg-nav-hover">
                  Abbrechen
                </button>
                <button type="button" onClick={save} disabled={saving} className="inline-flex items-center gap-1.5 rounded-lg bg-signal px-2.5 py-1.5 text-sm font-medium text-signal-foreground disabled:opacity-50" data-testid="save-box">
                  <Check className="size-4" /> Speichern
                </button>
              </>
            )}
            <DialogPrimitive.Close className="rounded-md p-1.5 hover:bg-nav-hover" aria-label="Foto schließen" disabled={editing}>
              <X className="size-4" />
            </DialogPrimitive.Close>
          </header>

          <div className="grid min-h-0 flex-1 md:grid-cols-[minmax(0,1fr)_260px]">
            <div className="flex min-h-0 items-center justify-center overflow-auto p-3">
              <div ref={imageRef} className="relative max-h-full max-w-full select-none" onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={plant.cabinetImageUrl(cabinet.id)} alt={cabinet.title} className="block max-h-[calc(100vh-11rem)] max-w-full object-contain" draggable={false} />
                {cabinet.hotspots.map((hotspot) => {
                  const isActive = hotspot.id === activeId;
                  if (isActive && editing && draft) return null;
                  const lit = isReferenced(hotspot);
                  return (
                    <button
                      key={hotspot.id}
                      type="button"
                      onClick={() => !editing && setActiveId(isActive ? null : hotspot.id)}
                      aria-label={`${hotspot.tag || "Bauteil ohne Kennzeichen"}${lit ? ", in der Antwort referenziert" : ""}`}
                      aria-pressed={isActive}
                      data-hotspot={hotspot.id}
                      className={cn(
                        "absolute rounded-sm border-2 text-[11px] font-semibold leading-none",
                        lit ? "border-signal bg-signal/30" : "border-white/80 bg-transparent hover:bg-white/10",
                        isActive && "ring-2 ring-primary ring-offset-1 ring-offset-black/50",
                      )}
                      style={styleOf(hotspot)}
                    >
                      <span className={cn("absolute -top-0.5 left-0 -translate-y-full rounded-t px-1 py-0.5", lit ? "bg-signal text-signal-foreground" : "bg-white/85 text-black")}>{hotspot.tag || "?"}</span>
                    </button>
                  );
                })}
                {editing && draft && (
                  <div
                    role="group"
                    aria-label={`Rahmen von ${active?.tag || "Bauteil"} bearbeiten`}
                    tabIndex={0}
                    data-testid="edit-frame"
                    className="absolute cursor-move rounded-sm border-2 border-signal bg-signal/20 outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    style={styleOf(draft)}
                    onPointerDown={(e) => onPointerDown(e, "move")}
                    ref={(el) => el?.focus()}
                  >
                    {(["nw", "ne", "sw", "se"] as Handle[]).map((handle) => (
                      <span
                        key={handle}
                        onPointerDown={(e) => onPointerDown(e, handle)}
                        aria-hidden
                        className={cn(
                          "absolute size-3.5 rounded-sm border border-black/40 bg-signal",
                          handle === "nw" && "-top-1.5 -left-1.5 cursor-nwse-resize",
                          handle === "ne" && "-top-1.5 -right-1.5 cursor-nesw-resize",
                          handle === "sw" && "-bottom-1.5 -left-1.5 cursor-nesw-resize",
                          handle === "se" && "-right-1.5 -bottom-1.5 cursor-nwse-resize",
                        )}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
            <aside className="min-h-0 overflow-y-auto border-t border-[#2a2f39] md:border-t-0 md:border-l">
              <ul className="divide-y divide-[#2a2f39]" aria-label="Markierte Bauteile">
                {cabinet.hotspots.map((h) => (
                  <li key={h.id}>
                    <button
                      type="button"
                      onClick={() => !editing && setActiveId(h.id)}
                      aria-current={h.id === activeId ? "true" : undefined}
                      className={cn("flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-nav-hover", h.id === activeId && "bg-nav-hover")}
                    >
                      <span className={cn("size-2 shrink-0 rounded-sm", isReferenced(h) ? "bg-signal" : "border border-white/70")} aria-hidden />
                      <span className="font-mono font-semibold">{h.tag || "?"}</span>
                      <span className="min-w-0 flex-1 truncate text-nav-foreground">{h.label || h.kind}</span>
                      <span className="text-[11px] text-nav-foreground">{h.origin === "manual" ? "manuell" : h.confidence != null ? `${Math.round(h.confidence * 100)} %` : ""}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </aside>
          </div>
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  );
}
