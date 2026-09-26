"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Fault, FaultInput } from "@/lib/api";

const EMPTY: FaultInput = { code: "", symptom: "", cause: "", fix: "", doc_ref: "", tags: [] };

/** Fehlereintrag anlegen oder bearbeiten. */
export function FaultDialog({
  fault,
  onClose,
  onSave,
}: {
  fault: Fault | "new" | null;
  onClose: () => void;
  onSave: (body: FaultInput) => Promise<void>;
}) {
  return (
    <Dialog open={fault !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="rounded-none sm:max-w-xl">
        {fault !== null && <FaultForm key={fault === "new" ? "new" : fault.id} fault={fault} onClose={onClose} onSave={onSave} />}
      </DialogContent>
    </Dialog>
  );
}

function FaultForm({ fault, onClose, onSave }: { fault: Fault | "new"; onClose: () => void; onSave: (body: FaultInput) => Promise<void> }) {
  const [form, setForm] = useState<FaultInput>(() =>
    fault === "new"
      ? EMPTY
      : { code: fault.code, symptom: fault.symptom, cause: fault.cause, fix: fault.fix, doc_ref: fault.doc_ref, tags: fault.tags },
  );
  const [tags, setTags] = useState(form.tags.join(", "));
  const [saving, setSaving] = useState(false);
  const set = (key: keyof FaultInput) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [key]: event.target.value });

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      await onSave({ ...form, tags: tags.split(",").map((t) => t.trim()).filter(Boolean) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-3">
      <DialogHeader>
        <DialogTitle className="font-mono uppercase tracking-[0.04em]">{fault === "new" ? "Neuer Fehlereintrag" : `Fehler ${fault.code}`}</DialogTitle>
      </DialogHeader>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="grid gap-1">
          <Label htmlFor="f-code">Code</Label>
          <Input id="f-code" value={form.code} onChange={set("code")} placeholder="E217" className="font-mono" />
        </div>
        <div className="grid gap-1">
          <Label htmlFor="f-ref">Doku-Verweis</Label>
          <Input id="f-ref" value={form.doc_ref} onChange={set("doc_ref")} placeholder="Stromlaufplan Blatt 4" />
        </div>
      </div>
      <div className="grid gap-1">
        <Label htmlFor="f-symptom">Symptom</Label>
        <Input id="f-symptom" value={form.symptom} onChange={set("symptom")} required />
      </div>
      <div className="grid gap-1">
        <Label htmlFor="f-cause">Ursache</Label>
        <Textarea id="f-cause" value={form.cause} onChange={set("cause")} rows={2} />
      </div>
      <div className="grid gap-1">
        <Label htmlFor="f-fix">Behebung</Label>
        <Textarea id="f-fix" value={form.fix} onChange={set("fix")} rows={3} />
      </div>
      <div className="grid gap-1">
        <Label htmlFor="f-tags">Beteiligte BMK</Label>
        <Input id="f-tags" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="-F2, -M1" className="font-mono" />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Abbrechen
        </Button>
        <Button type="submit" disabled={saving}>
          Speichern
        </Button>
      </DialogFooter>
    </form>
  );
}
