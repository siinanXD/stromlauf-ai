"use client";

import { Lock, Pencil, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { CitationChip } from "@/components/chat/CitationChip";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { wissen, type MachineNote } from "@/lib/api";
import { belegText, QUELLE_LABELS, sortiert } from "./wissen";

const ICON_BUTTON = "grid size-11 shrink-0 place-items-center rounded-xs text-muted-foreground hover:text-foreground";

/** Gelernte Sätze einer Maschine: ansehen, bearbeiten (sperrt den Satz), löschen. */
export function WissenTab({ machineId }: { machineId: string }) {
  // key: bei anderer Maschine beginnt der Zustand (Liste, Bearbeiten, Dialog) von vorn
  return <WissenListe key={machineId} machineId={machineId} />;
}

function WissenListe({ machineId }: { machineId: string }) {
  const [notes, setNotes] = useState<MachineNote[] | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirm, setConfirm] = useState<MachineNote | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const editButtons = useRef(new Map<string, HTMLButtonElement>());

  useEffect(() => {
    let cancelled = false;
    wissen
      .list(machineId)
      .then((list) => !cancelled && setNotes(list))
      .catch((err: Error) => {
        if (cancelled) return;
        setLoadError(err.message);
        toast.error(`Wissen nicht geladen: ${err.message}`);
      });
    return () => {
      cancelled = true;
    };
  }, [machineId, attempt]);

  function closeEdit(noteId: string) {
    setEditId(null);
    editButtons.current.get(noteId)?.focus();
  }

  async function save(note: MachineNote) {
    setSaving(true);
    try {
      const updated = await wissen.patch(machineId, note.id, { text: draft });
      setNotes((list) => list && list.map((n) => (n.id === note.id ? updated : n)));
      closeEdit(note.id);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(note: MachineNote) {
    setConfirm(null);
    try {
      await wissen.remove(machineId, note.id);
      setNotes((list) => list && list.filter((n) => n.id !== note.id));
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  if (loadError !== null)
    return (
      <div className="space-y-2">
        <p className="text-muted-foreground">Wissen nicht geladen: {loadError}</p>
        <Button variant="outline" className="h-11 border-line" onClick={() => {
            setLoadError(null);
            setAttempt((n) => n + 1);
          }}>
          Erneut laden
        </Button>
      </div>
    );
  if (notes === null) return <p className="text-muted-foreground">Lade Wissen …</p>;

  return (
    <section className="max-w-4xl space-y-3">
      <p className="text-[13px] text-muted-foreground">
        Gesperrte Sätze (🔒) hat ein Mensch bestätigt oder korrigiert; sie gewinnen gegen neue Sätze.
      </p>
      {notes.length === 0 ? (
        <p className="text-muted-foreground">Noch nichts gelernt. Ein Lauf auf /ablauf oder ein Chat mit Belegen füllt die Liste.</p>
      ) : (
        <ul aria-label="Gelernte Sätze" className="divide-y divide-border border border-line bg-card">
          {sortiert(notes).map((note) => (
            <li key={note.id} data-testid="wissen-satz" className="flex items-start gap-2 px-3 py-2 text-[13px]">
              <div className="min-w-0 flex-1 space-y-1.5">
                {editId === note.id ? (
                  <div className="space-y-2">
                    <Textarea aria-label="Satz" value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} />
                    <div className="flex gap-2">
                      <Button size="sm" disabled={saving || !draft.trim()} onClick={() => void save(note)}>
                        Speichern
                      </Button>
                      <Button size="sm" variant="outline" className="border-line" disabled={saving} onClick={() => closeEdit(note.id)}>
                        Abbrechen
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p>{note.text}</p>
                )}
                <div className="flex flex-wrap items-center gap-1">
                  {note.belege.map((b) => (
                    <CitationChip key={`${b.document_id}-${b.page ?? ""}`} label={belegText(b)} title={b.filename} />
                  ))}
                  <span className="rounded-xs border border-line px-1.5 font-mono text-[11px] leading-5 text-muted-foreground">
                    {QUELLE_LABELS[note.quelle]}
                  </span>
                  {note.gesperrt && <Lock aria-label="gesperrt" className="size-3.5 text-muted-foreground" />}
                </div>
              </div>
              <button
                type="button"
                aria-label="Satz bearbeiten"
                ref={(el) => {
                  if (el) editButtons.current.set(note.id, el);
                  else editButtons.current.delete(note.id);
                }}
                className={ICON_BUTTON}
                onClick={() => {
                  setEditId(note.id);
                  setDraft(note.text);
                }}
              >
                <Pencil className="size-4" />
              </button>
              <button type="button" aria-label="Satz löschen" className={`${ICON_BUTTON} hover:text-danger`} onClick={() => setConfirm(note)}>
                <Trash2 className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={confirm !== null} onOpenChange={(open) => !open && setConfirm(null)}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Satz löschen?</DialogTitle>
            <DialogDescription>{confirm ? `„${confirm.text}“ wird aus dem Wissen dieser Maschine gelöscht.` : ""}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" className="h-11" onClick={() => setConfirm(null)}>
              Abbrechen
            </Button>
            <Button type="button" className="h-11" onClick={() => confirm && void remove(confirm)}>
              Löschen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
