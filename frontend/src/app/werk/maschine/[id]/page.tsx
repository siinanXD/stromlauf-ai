"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AppNav } from "@/components/AppNav";
import { CabinetEditor } from "@/components/CabinetEditor";
import { PageViewer, type PageTarget } from "@/components/PageViewer";
import { api, MACHINE_TYPE_LABELS, plant, type Fault, type FaultInput, type KnowledgeSource, type MachineDetail } from "@/lib/api";

const EMPTY_FAULT: FaultInput = { code: "", symptom: "", cause: "", fix: "", doc_ref: "", tags: [] };

export default function MachinePage() {
  const { id } = useParams<{ id: string }>();
  const [highlightTag, setHighlightTag] = useState<string | null>(() =>
    typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("tag"),
  );
  const [machine, setMachine] = useState<MachineDetail | null>(null);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [imageBust, setImageBust] = useState(0);
  const [pageTarget, setPageTarget] = useState<PageTarget | null>(null);
  const [editing, setEditing] = useState<Fault | "new" | null>(null);
  const [form, setForm] = useState<FaultInput>(EMPTY_FAULT);
  const [cabinetTitle, setCabinetTitle] = useState("Schaltschrank");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => plant.getMachine(id).then(setMachine).catch((err) => setError(err.message)), [id]);

  useEffect(() => {
    load();
    api.listSources().then(setSources).catch(() => {});
  }, [load]);

  async function update(body: Parameters<typeof plant.updateMachine>[1]) {
    await plant.updateMachine(id, body).catch((err) => setError(err.message));
    load();
  }

  async function uploadImage(file: File | undefined) {
    if (!file) return;
    await plant.uploadMachineImage(id, file).catch((err) => setError(err.message));
    setImageBust(Date.now());
    load();
  }

  async function uploadCabinet(file: File | undefined) {
    if (!file) return;
    await plant.uploadCabinet(id, file, cabinetTitle).catch((err) => setError(err.message));
    load();
  }

  function startEdit(fault: Fault | "new") {
    setEditing(fault);
    setForm(fault === "new" ? EMPTY_FAULT : { code: fault.code, symptom: fault.symptom, cause: fault.cause, fix: fault.fix, doc_ref: fault.doc_ref, tags: fault.tags });
  }

  async function saveFault(event: React.FormEvent) {
    event.preventDefault();
    try {
      if (editing === "new") await plant.createFault(id, form);
      else if (editing) await plant.updateFault(editing.id, form);
      setEditing(null);
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function deleteFault(fault: Fault) {
    if (!confirm(`Fehlereintrag „${fault.code || fault.symptom}“ löschen?`)) return;
    await plant.deleteFault(fault.id).catch((err) => setError(err.message));
    load();
  }

  if (!machine) {
    return (
      <div className="flex h-full flex-col">
        <div className="border-b border-border bg-surface">
          <AppNav />
        </div>
        <p className="p-8 text-muted">{error ?? "Lade Maschine …"}</p>
      </div>
    );
  }

  const chatHref = machine.source_id ? `/?source=${machine.source_id}` : "/";

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border bg-surface">
        <AppNav />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl space-y-8 px-4 py-6">
          <div className="text-sm text-muted">
            <Link href="/werk" className="hover:text-text">
              Werk
            </Link>{" "}
            / {MACHINE_TYPE_LABELS[machine.machine_type]}
          </div>

          {error && <p className="rounded-md bg-accent-soft px-3 py-2 text-sm text-danger">{error}</p>}

          {/* Kopf: Foto + Stammdaten */}
          <section className="grid gap-6 md:grid-cols-[280px_minmax(0,1fr)]">
            <label className="group relative block aspect-[4/3] cursor-pointer overflow-hidden rounded-xl border border-border bg-surface-2">
              {machine.has_image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={plant.machineImageUrl(machine.id, imageBust)} alt={machine.name} className="h-full w-full object-cover" />
              ) : (
                <span className="grid h-full place-items-center text-sm text-muted">Foto der Maschine hochladen</span>
              )}
              <span className="absolute inset-x-0 bottom-0 bg-black/50 py-1 text-center text-xs text-white opacity-0 group-hover:opacity-100">
                Bild ändern
              </span>
              <input type="file" accept="image/*" className="hidden" onChange={(event) => uploadImage(event.target.files?.[0])} />
            </label>

            <div className="space-y-3">
              <input
                key={machine.name}
                defaultValue={machine.name}
                onBlur={(event) => event.target.value.trim() && event.target.value !== machine.name && update({ name: event.target.value.trim() })}
                className="w-full rounded-md border border-transparent bg-transparent text-2xl font-semibold tracking-tight hover:border-border focus:border-border"
              />
              <textarea
                key={machine.description}
                defaultValue={machine.description}
                placeholder="Beschreibung: Aufgabe, Baujahr, Besonderheiten …"
                rows={3}
                onBlur={(event) => event.target.value !== machine.description && update({ description: event.target.value })}
                className="w-full resize-none rounded-md border border-border bg-bg px-2 py-1.5 text-sm"
              />
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <label className="flex items-center gap-2">
                  <span className="text-muted">Doku:</span>
                  <select
                    value={machine.source_id ?? ""}
                    onChange={(event) => (event.target.value ? update({ source_id: event.target.value }) : update({ clear_source: true }))}
                    className="rounded-md border border-border bg-bg px-2 py-1"
                  >
                    <option value="">keine Wissensquelle</option>
                    {sources.map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.name} ({source.document_count})
                      </option>
                    ))}
                  </select>
                </label>
                <Link href={chatHref} className="rounded-md bg-accent px-3 py-1.5 font-medium text-accent-fg">
                  Chat zu dieser Maschine
                </Link>
              </div>
            </div>
          </section>

          {/* Fehlerliste */}
          <section>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Fehlerliste</h2>
              <button onClick={() => startEdit("new")} className="rounded-md border border-border px-2.5 py-1 text-sm hover:bg-surface-2">
                + Eintrag
              </button>
            </div>
            {machine.faults.length === 0 && !editing && (
              <p className="mt-2 text-sm text-muted">Noch keine Einträge. Bekannte Störungen mit Ursache und Behebung festhalten.</p>
            )}
            {machine.faults.length > 0 && (
              <div className="mt-2 overflow-x-auto rounded-xl border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-surface-2 text-left text-xs uppercase tracking-wider text-muted">
                    <tr>
                      <th className="px-3 py-2">Code</th>
                      <th className="px-3 py-2">Symptom</th>
                      <th className="px-3 py-2">Ursache</th>
                      <th className="px-3 py-2">Behebung</th>
                      <th className="px-3 py-2">Doku / BMK</th>
                      <th className="px-3 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {machine.faults.map((fault) => (
                      <tr key={fault.id} className="border-t border-border align-top">
                        <td className="px-3 py-2 font-mono">{fault.code}</td>
                        <td className="px-3 py-2">{fault.symptom}</td>
                        <td className="px-3 py-2">{fault.cause}</td>
                        <td className="px-3 py-2">{fault.fix}</td>
                        <td className="px-3 py-2 text-muted">
                          {fault.doc_ref}
                          {fault.tags.length > 0 && (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {fault.tags.map((tag) => (
                                <button key={tag} onClick={() => setHighlightTag(tag)} className="rounded bg-surface-2 px-1 font-mono text-xs hover:bg-accent-soft">
                                  {tag}
                                </button>
                              ))}
                            </div>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-right">
                          <button onClick={() => startEdit(fault)} className="text-muted hover:text-text">
                            ✎
                          </button>
                          <button onClick={() => deleteFault(fault)} className="ml-2 text-muted hover:text-danger">
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {editing && (
              <form onSubmit={saveFault} className="mt-3 grid gap-2 rounded-xl border border-border bg-surface p-3 text-sm md:grid-cols-2">
                <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="Code, z. B. E217" className="rounded-md border border-border bg-bg px-2 py-1.5 font-mono" />
                <input value={form.doc_ref} onChange={(e) => setForm({ ...form, doc_ref: e.target.value })} placeholder="Doku-Verweis, z. B. Stromlaufplan Blatt 4" className="rounded-md border border-border bg-bg px-2 py-1.5" />
                <input value={form.symptom} onChange={(e) => setForm({ ...form, symptom: e.target.value })} placeholder="Symptom" className="rounded-md border border-border bg-bg px-2 py-1.5 md:col-span-2" />
                <input value={form.cause} onChange={(e) => setForm({ ...form, cause: e.target.value })} placeholder="Ursache" className="rounded-md border border-border bg-bg px-2 py-1.5" />
                <input value={form.fix} onChange={(e) => setForm({ ...form, fix: e.target.value })} placeholder="Behebung" className="rounded-md border border-border bg-bg px-2 py-1.5" />
                <input
                  value={form.tags.join(", ")}
                  onChange={(e) => setForm({ ...form, tags: e.target.value.split(",").map((t) => t.trim()).filter(Boolean) })}
                  placeholder="Beteiligte BMK, z. B. -F2, -M1"
                  className="rounded-md border border-border bg-bg px-2 py-1.5 font-mono md:col-span-2"
                />
                <div className="flex gap-2 md:col-span-2">
                  <button className="rounded-md bg-accent px-3 py-1.5 font-medium text-accent-fg">Speichern</button>
                  <button type="button" onClick={() => setEditing(null)} className="rounded-md border border-border px-3 py-1.5">
                    Abbrechen
                  </button>
                </div>
              </form>
            )}
          </section>

          {/* Schaltschraenke */}
          <section>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Schaltschrank</h2>
              <div className="flex items-center gap-2 text-sm">
                <input
                  value={cabinetTitle}
                  onChange={(event) => setCabinetTitle(event.target.value)}
                  className="w-44 rounded-md border border-border bg-bg px-2 py-1"
                  aria-label="Titel des Schaltschrankbilds"
                />
                <label className="cursor-pointer rounded-md border border-border px-2.5 py-1 hover:bg-surface-2">
                  + Foto oder Aufbauplan
                  <input type="file" accept="image/*" className="hidden" onChange={(event) => uploadCabinet(event.target.files?.[0])} />
                </label>
              </div>
            </div>
            {machine.cabinets.length === 0 && (
              <p className="mt-2 text-sm text-muted">
                Foto vom offenen Schaltschrank oder den Aufbauplan hochladen, Bauteile markieren (oder erkennen lassen) und per Klick zur Doku springen.
              </p>
            )}
            <div className="mt-3 space-y-8">
              {machine.cabinets.map((cabinet) => (
                <div key={cabinet.id}>
                  <div className="mb-2 flex items-center gap-3">
                    <h3 className="font-medium">{cabinet.title}</h3>
                    <span className="text-xs text-muted">
                      {cabinet.width}×{cabinet.height}
                    </span>
                    <button
                      onClick={async () => {
                        if (!confirm(`„${cabinet.title}“ mit ${cabinet.hotspots.length} Markierungen löschen?`)) return;
                        await plant.deleteCabinet(cabinet.id).catch((err) => setError(err.message));
                        load();
                      }}
                      className="ml-auto text-sm text-muted hover:text-danger"
                    >
                      löschen
                    </button>
                  </div>
                  <CabinetEditor cabinet={cabinet} machineId={machine.id} highlightTag={highlightTag} onChanged={load} onOpenPage={setPageTarget} />
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>

      {pageTarget && <PageViewer target={pageTarget} onClose={() => setPageTarget(null)} />}
    </div>
  );
}
