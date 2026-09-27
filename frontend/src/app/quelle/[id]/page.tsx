"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { api, DOC_TYPE_LABELS, type DocType, type SourceProfile } from "@/lib/api";
import { cn } from "@/lib/utils";

const TAG_TYPE_LABELS = { device: "Betriebsmittel", terminal: "Klemme", plc_address: "SPS-Adresse" } as const;
const TH = "px-3 py-2 text-left font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground";
const SECTION = "font-mono text-sm font-semibold uppercase tracking-[0.06em]";

/** Steckbrief einer Wissensquelle: welche Dokumente da sind, wie sie zusammenpassen, was fehlt. Ohne KI-Kosten. */
export default function SourceProfilePage() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<SourceProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [onlyGaps, setOnlyGaps] = useState(false);

  useEffect(() => {
    api
      .getSourceProfile(id)
      .then(setProfile)
      .catch((err) => setError((err as Error).message));
  }, [id]);

  const presentTypes = useMemo(() => (profile?.doc_types ?? []).filter((t) => t.present).map((t) => t.doc_type), [profile]);
  const gapTags = useMemo(() => new Set((profile?.gaps ?? []).map((g) => g.tag)), [profile]);
  const groups = useMemo(() => {
    const byKind = new Map<string, { message: string; tags: string[] }>();
    for (const gap of profile?.gaps ?? []) {
      const group = byKind.get(gap.kind) ?? { message: gap.message, tags: [] };
      group.tags.push(gap.tag);
      byKind.set(gap.kind, group);
    }
    return Array.from(byKind.entries());
  }, [profile]);
  const rows = useMemo(() => {
    const needle = query.trim().toUpperCase();
    return (profile?.coverage ?? []).filter((c) => (!needle || c.tag.toUpperCase().includes(needle)) && (!onlyGaps || gapTags.has(c.tag)));
  }, [profile, query, onlyGaps, gapTags]);

  const name = profile?.source_name ?? "…";
  return (
    <AppShell breadcrumb={[{ label: "Chat", href: "/" }, { label: "Wissensquelle" }, { label: name }]}>
      <div className="flex h-full flex-col">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-4 py-2">
          <h1 className="font-mono text-lg font-semibold uppercase tracking-[0.04em]">Steckbrief {name}</h1>
          {profile && (
            <span className="text-sm text-muted-foreground">
              {profile.summary.devices} Betriebsmittel · {profile.summary.terminals} Klemmen · {profile.summary.plc_addresses} SPS-Adressen ·{" "}
              <span className={cn(profile.summary.gaps > 0 && "font-medium text-danger")}>
                {profile.summary.gaps === 0 ? "keine Lücken" : `${profile.summary.gaps} Lücken`}
              </span>
              {profile.sheets.length > 0 && ` · Plan mit ${profile.sheets.length} Blättern`}
            </span>
          )}
        </div>
        {error && <p className="border-b border-border px-4 py-1.5 text-xs text-danger">{error}</p>}

        {profile && (
          <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-4 md:px-6">
            <section>
              <h2 className={SECTION}>Dokumente</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Sechs Dokumenttypen tragen zum Signalweg, zur Befundkarte und zum Chat bei. Fehlt einer, fehlen die Lückenregeln, die ihn brauchen.
              </p>
              <ul className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
                {profile.doc_types.map((t) => (
                  <li
                    key={t.doc_type}
                    className={cn("border p-3 text-sm", t.present ? "border-line bg-card" : "border-dashed border-border text-muted-foreground")}
                  >
                    <div className="font-medium">{DOC_TYPE_LABELS[t.doc_type]}</div>
                    {t.present ? (
                      <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                        {t.filenames.map((f) => (
                          <li key={f} className="truncate" title={f}>
                            {f}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="mt-1 text-xs">fehlt</div>
                    )}
                  </li>
                ))}
              </ul>
              {profile.documents.some((d) => d.status !== "ready" || d.doc_type === "other") && (
                <ul className="mt-2 text-xs text-muted-foreground">
                  {profile.documents
                    .filter((d) => d.status !== "ready" || d.doc_type === "other")
                    .map((d) => (
                      <li key={d.id}>
                        {d.filename}: {DOC_TYPE_LABELS[d.doc_type as DocType] ?? d.doc_type}, {d.status === "ready" ? `${d.tag_count} Kennzeichen` : d.status}
                      </li>
                    ))}
                </ul>
              )}
            </section>

            <section>
              <h2 className={SECTION}>Lücken {profile.gaps.length > 0 && <span className="text-danger">{profile.gaps.length}</span>}</h2>
              {profile.gaps.length === 0 ? (
                <p className="mt-1 text-sm text-muted-foreground">Keine Widersprüche zwischen den vorhandenen Dokumenten.</p>
              ) : (
                <ul className="mt-2 space-y-3">
                  {groups.map(([kind, group]) => (
                    <li key={kind} className="border border-line bg-card p-3">
                      <div className="text-sm font-medium">
                        {group.message} <span className="text-muted-foreground">({group.tags.length})</span>
                      </div>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {group.tags.map((tag) => (
                          <button
                            key={tag}
                            type="button"
                            onClick={() => {
                              setQuery(tag);
                              setOnlyGaps(false);
                            }}
                            className="border border-border bg-background px-1.5 py-0.5 font-mono text-xs hover:border-primary hover:text-primary"
                            title="In der Abdeckung zeigen"
                          >
                            {tag}
                          </button>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <div className="flex flex-wrap items-center gap-3">
                <h2 className={SECTION}>Abdeckung</h2>
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Kennzeichen filtern: -K12, -X3:, E0."
                  aria-label="Kennzeichen filtern"
                  className="h-8 w-64 border border-border bg-background px-2 text-sm"
                />
                <label className="flex items-center gap-1.5 text-sm">
                  <input type="checkbox" checked={onlyGaps} onChange={(event) => setOnlyGaps(event.target.checked)} className="accent-[var(--primary)]" />
                  nur Lücken
                </label>
                <span className="text-xs text-muted-foreground">
                  {rows.length} von {profile.coverage.length}
                </span>
              </div>
              <table className="mt-2 w-full border-collapse text-sm">
                <thead className="sticky top-0 bg-card">
                  <tr className="border-b border-line">
                    <th className={TH}>Kennzeichen</th>
                    <th className={TH}>Art</th>
                    {presentTypes.map((t) => (
                      <th key={t} className={cn(TH, "text-right")}>
                        {DOC_TYPE_LABELS[t]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={`${row.tag_type}-${row.tag}`} className={cn("border-b border-border", gapTags.has(row.tag) && "bg-danger/5")}>
                      <td className="px-3 py-1.5 font-mono">{row.tag}</td>
                      <td className="px-3 py-1.5 text-muted-foreground">{TAG_TYPE_LABELS[row.tag_type]}</td>
                      {presentTypes.map((t) => (
                        <td key={t} className={cn("px-3 py-1.5 text-right tabular-nums", !row.docs[t] && "text-muted-foreground/50")}>
                          {row.docs[t] ?? "–"}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={2 + presentTypes.length} className="p-4 text-center text-muted-foreground">
                        Nichts passt zum Filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>

            <p className="text-xs text-muted-foreground">
              Zählwerte sind Fundstellen je Dokumenttyp. Lücken sind Regeln zwischen zwei Dokumenttypen; sie greifen nur, wenn beide vorhanden sind.
              Kennzeichen suchen: <Link href="/" className="text-primary hover:underline">Chat</Link> oder Strg+K.
            </p>
          </div>
        )}
      </div>
    </AppShell>
  );
}
