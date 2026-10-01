"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { prefetchFaultHits } from "@/components/answer/faultHitsStore";
import { MachineChatTab } from "@/components/machine/MachineChatTab";
import { api, type AnswerMeta, type MachineDetail, type MachineMap } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";
import { cn } from "@/lib/utils";

import {
  addPending,
  confirmPending,
  isTempId,
  mergeServer,
  newTempId,
  removeIncident,
  replaceIncident,
  type Incident,
  type IncidentFilter,
} from "./incidents";
import { IncidentList } from "./IncidentList";
import { levelOf, viewFromParams, type AufbauTab, type MachineView } from "./view";

// Gleiche Breite wie DETAIL_WIDTH in DetailPane.tsx; ein statischer Import wuerde das Nachladen aufheben
const DETAIL_WIDTH_CLASS = "lg:w-[min(560px,45%)]";

// Das Detail (Seitenansicht, Foto-Editor, Datenblatt) erst laden, wenn ein Block angetippt wird
const DetailPane = dynamic(() => import("./DetailPane").then((m) => m.DetailPane), {
  loading: () => <div className={cn("flex-1 animate-pulse bg-secondary/40 lg:flex-none", DETAIL_WIDTH_CLASS)} aria-busy="true" />,
});

export type Navigate = (next: MachineView, mode: "push" | "replace") => void;

/**
 * Bereich Stoerfaelle: Liste | Chat | Detail. Ab 1024 px drei Spalten (Detail erst nach Antippen eines Blocks),
 * darunter eine Ebene aus ?fall= und ?detail=. Beim Oeffnen laedt nur die Liste; ein neuer Stoerfall steht sofort
 * darin, der Chat und die Fehlerliste starten parallel.
 */
export function IncidentWorkspace({
  machine,
  view,
  navigate,
  goBack,
  map,
  referencedTags,
  onMeta,
  onShowInModel,
  onGoToAufbau,
  onMachineChanged,
}: {
  machine: MachineDetail;
  view: MachineView;
  navigate: Navigate;
  /** Eine Ebene zurueck, wie die Zurueck-Geste des Browsers. */
  goBack: () => void;
  map: MachineMap | null | undefined;
  referencedTags: string[];
  onMeta: (meta: AnswerMeta) => void;
  onShowInModel: (tags: string[]) => void;
  onGoToAufbau: (tab: AufbauTab) => void;
  onMachineChanged: () => void;
}) {
  const sourceId = machine.source_id;
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "failed">(sourceId ? "loading" : "ready");
  const [filter, setFilter] = useState<IncidentFilter>("open");
  /** Meldungen neuer Stoerfaelle, die ihr Chat beim Erscheinen sendet (je vorlaeufiger ID). */
  const [sends, setSends] = useState<Record<string, string>>({});
  /** Echte ID -> vorlaeufige ID: der Chat behaelt seinen Zustand, wenn die ID wechselt. */
  const [aliases, setAliases] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    if (!sourceId) return Promise.resolve();
    return api
      .listConversations(sourceId)
      .then((list) => {
        setIncidents((current) => mergeServer(current, list));
        setStatus("ready");
      })
      .catch(() => setStatus((s) => (s === "ready" ? s : "failed")));
  }, [sourceId]);

  useEffect(() => {
    void load();
  }, [load]);

  const level = levelOf(view);
  const fall = view.fall;
  // Die URL kann kurz noch die vorlaeufige ID tragen, waehrend die Liste schon die echte hat (aliases)
  const incident = fall ? (incidents.find((i) => i.id === fall || aliases[i.id] === fall) ?? null) : null;
  const chatKey = incident ? (aliases[incident.id] ?? incident.id) : null;

  // Nach einem Neuladen gibt es vorlaeufige IDs nicht mehr: zurueck zur Liste
  const staleTemp = status === "ready" && Boolean(fall) && isTempId(fall) && !incident;
  useEffect(() => {
    if (staleTemp) navigate({ ...view, fall: null, detail: null }, "replace");
  }, [staleTemp, navigate, view]);

  const openDetail = useCallback((detail: DetailRef) => navigate({ ...view, detail }, "push"), [navigate, view]);
  const openIncident = useCallback((id: string) => navigate({ ...view, fall: id, detail: null }, "push"), [navigate, view]);

  // Esc schliesst das Detail (die Seitenansicht und offene Dialoge regeln Esc selbst)
  useEffect(() => {
    if (!view.detail || view.detail.kind === "plan") return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      const el = event.target as HTMLElement | null;
      if (el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))) return;
      if (document.querySelector('[role="dialog"][data-state="open"]')) return;
      goBack();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view.detail, goBack]);

  function create(text: string) {
    if (!sourceId) return;
    const id = newTempId();
    setIncidents((list) => addPending(list, { id, title: text, sourceId }));
    setSends((current) => ({ ...current, [id]: text }));
    setFilter("open");
    // Fehlerliste sofort, noch vor dem Chat: der erste Block steht in unter einer Sekunde
    void prefetchFaultHits(machine.id, text);
    navigate({ ...view, fall: id, detail: null }, "push");
  }

  function confirmed(key: string, id: string, title: string) {
    setIncidents((list) => confirmPending(list, key, { id, title }));
    setSends((current) => {
      if (!(key in current)) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
    if (id !== key) setAliases((current) => ({ ...current, [id]: key }));
    // Nur umschreiben, wenn der Stoerfall noch offen ist; die URL ist die Wahrheit, nicht ein alter Zustand
    const current = viewFromParams(new URLSearchParams(window.location.search));
    if (current.fall === key && id !== key) navigate({ ...current, fall: id }, "replace");
  }

  async function patch(target: Incident, change: { outcome: "open" | "resolved"; finding?: string }): Promise<boolean> {
    try {
      const updated = await api.patchConversation(target.id, change);
      setIncidents((list) =>
        replaceIncident(list, {
          ...target,
          ...updated,
          outcome: updated?.outcome ?? change.outcome,
          finding: updated?.finding ?? change.finding ?? target.finding ?? "",
        }),
      );
      setFilter(change.outcome);
      return true;
    } catch {
      toast.error(change.outcome === "resolved" ? "Erledigt konnte nicht gespeichert werden." : "Wieder öffnen hat nicht geklappt.", {
        action: { label: "Erneut versuchen", onClick: () => void patch(target, change) },
      });
      return false;
    }
  }

  async function remove(target: Incident): Promise<boolean> {
    try {
      await api.deleteConversation(target.id);
      setIncidents((list) => removeIncident(list, target.id));
      navigate({ ...view, fall: null, detail: null }, "replace");
      return true;
    } catch {
      toast.error("Löschen hat nicht geklappt.", { action: { label: "Erneut versuchen", onClick: () => void remove(target) } });
      return false;
    }
  }

  const activeReference = view.detail?.kind === "plan" && view.detail.target.reference ? `${view.detail.target.documentId}${view.detail.target.reference}` : null;

  return (
    <div className="flex min-h-0 flex-1" data-testid="incident-workspace" data-level={level}>
      <div className={cn("min-h-0 w-full flex-col bg-card lg:flex lg:w-[260px] lg:shrink-0 lg:border-r lg:border-border 2xl:w-[300px]", level === "list" ? "flex" : "hidden")}>
        <IncidentList
          incidents={incidents}
          loading={status === "loading"}
          failed={status === "failed"}
          onRetry={() => {
            setStatus("loading");
            void load();
          }}
          activeId={incident?.id ?? fall}
          filter={filter}
          onFilter={setFilter}
          onCreate={create}
          onSelect={openIncident}
          unavailable={
            sourceId
              ? undefined
              : { reason: "Keine Dokumentation verknüpft. Ohne Doku gibt es keine belegten Antworten.", action: { label: "Dokumente verknüpfen", onClick: () => onGoToAufbau("dokumente") } }
          }
        />
      </div>

      <div className={cn("min-h-0 min-w-0 flex-1 flex-col lg:flex", level === "chat" ? "flex" : "hidden")}>
        {incident && chatKey ? (
          <MachineChatTab
            key={chatKey}
            machine={machine}
            incident={incident}
            conversationId={isTempId(incident.id) ? null : incident.id}
            autoSend={sends[chatKey] !== undefined ? { key: chatKey, text: sends[chatKey] } : undefined}
            activeReference={activeReference}
            onConversationId={(id, title) => confirmed(chatKey, id, title)}
            onConversationsChanged={() => void load()}
            onOpenDetail={openDetail}
            onOpenIncident={openIncident}
            onShowInModel={onShowInModel}
            onMeta={onMeta}
            onBack={goBack}
            onResolve={(finding) => patch(incident, { outcome: "resolved", finding })}
            onReopen={() => patch(incident, { outcome: "open" })}
            onDelete={() => remove(incident)}
          />
        ) : fall && status === "loading" ? (
          <div className="flex-1 animate-pulse bg-secondary/40" aria-busy="true" />
        ) : fall ? (
          <div className="space-y-3 p-6 text-sm" data-testid="incident-missing">
            <p className="text-muted-foreground">Diesen Störfall gibt es hier nicht (mehr). Er wurde gelöscht oder gehört zu einer anderen Doku.</p>
            <button type="button" onClick={goBack} className="min-h-11 rounded-lg border border-border px-3 font-medium hover:border-primary">
              Zur Liste
            </button>
          </div>
        ) : (
          <div className="hidden flex-1 items-center justify-center p-8 text-center lg:flex" data-testid="incident-none">
            <p className="max-w-sm text-sm text-muted-foreground">
              {sourceId
                ? "Wähle links einen Störfall oder tippe links oben eine Meldung vom Bedienpanel oder ein Symptom ein und drücke Enter."
                : "Ohne verknüpfte Dokumentation gibt es keine Störfälle. Links lässt sich die Doku verknüpfen."}
            </p>
          </div>
        )}
      </div>

      {view.detail && (
        <DetailPane
          detail={view.detail}
          machine={machine}
          map={map}
          referencedTags={referencedTags}
          onOpenDetail={openDetail}
          onClose={goBack}
          onGoToAufbau={onGoToAufbau}
          onMachineChanged={onMachineChanged}
        />
      )}
    </div>
  );
}

