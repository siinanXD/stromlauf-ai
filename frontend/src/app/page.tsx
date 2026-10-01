"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ChatNotice, homeNotice } from "@/components/chat/chatError";
import { ChatPanel, ExampleQuestions } from "@/components/chat/ChatPanel";
import { PageViewer, type PageTarget } from "@/components/PageViewer";
import { Sidebar } from "@/components/Sidebar";
import { api, API_URL, type Conversation, type Health, type KnowledgeSource } from "@/lib/api";

const EXAMPLES = [
  "Wo ist Schütz -K12 verbaut und was schaltet es?",
  "Welcher SPS-Eingang hängt an Klemme -X1:5 und in welchem Netzwerk wird er verwendet?",
  "Erkläre mir FB 10 Netzwerk für Netzwerk.",
  "Motor -M1 läuft nicht an: welche Bedingungen müssen erfüllt sein?",
];

/** Werksweiter Chat: Wissensquellen frei waehlbar. Der Chat je Maschine sitzt auf der Maschinenseite (Tab Chat). */
export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [initialInput, setInitialInput] = useState("");
  const [pageTarget, setPageTarget] = useState<PageTarget | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const loadSources = useCallback(() => api.listSources().then(setSources).catch(() => {}), []);
  const loadConversations = useCallback(() => api.listConversations().then(setConversations).catch(() => {}), []);

  useEffect(() => {
    api
      .health()
      .then((result) => {
        setHealth(result);
        loadSources();
        loadConversations();
        // Von aussen: /?source=<id>&q=<Frage> waehlt die Wissensquelle vor und fuellt die Frage ein
        const params = new URLSearchParams(window.location.search);
        const preset = params.get("source");
        if (preset) setSelectedSourceIds([preset]);
        const question = params.get("q");
        if (question) setInitialInput(question);
      })
      // Technische Angaben nur fuer "Details"; angezeigt wird ein Satz (ChatNotice)
      .catch((err: Error) => setBackendError(`Backend unter ${API_URL} nicht erreichbar: ${err.message}`));
  }, [loadSources, loadConversations]);

  function selectConversation(conversation: Conversation) {
    setConversationId(conversation.id);
    setSelectedSourceIds(conversation.source_ids.filter((id) => sources.some((s) => s.id === id)));
    setSidebarOpen(false);
  }

  function newConversation() {
    setConversationId(null);
    setSidebarOpen(false);
  }

  async function deleteConversation(conversation: Conversation) {
    if (!confirm(`Chat „${conversation.title}“ löschen?`)) return;
    await api.deleteConversation(conversation.id).catch(() => {});
    if (conversation.id === conversationId) newConversation();
    loadConversations();
  }

  const notice = homeNotice({ health, unreachable: backendError });
  const banner = notice ? <ChatNotice raw={notice} /> : null;

  return (
    <AppShell breadcrumb={[{ label: "Chat" }]}>
      <div className="flex h-full">
        <aside
          className={`fixed inset-y-0 left-0 z-40 w-80 max-w-[88vw] border-r border-border bg-card transition-transform md:static md:translate-x-0 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <Sidebar
            sources={sources}
            selectedSourceIds={selectedSourceIds}
            onToggleSource={(id) => setSelectedSourceIds((current) => (current.includes(id) ? current.filter((s) => s !== id) : [...current, id]))}
            onSourcesChanged={loadSources}
            conversations={conversations}
            activeConversationId={conversationId}
            onSelectConversation={selectConversation}
            onNewConversation={newConversation}
            onDeleteConversation={deleteConversation}
            onOpenPage={setPageTarget}
          />
        </aside>
        {sidebarOpen && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setSidebarOpen(false)} />}

        <main className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center gap-3 border-b border-border px-4 py-2.5 md:hidden">
            <button onClick={() => setSidebarOpen(true)} aria-label="Menü öffnen" className="text-xl">
              ☰
            </button>
            <span className="font-semibold">Stromlauf AI</span>
          </header>
          <ChatPanel
            scope={{ sourceIds: selectedSourceIds }}
            conversationId={conversationId}
            onConversationId={setConversationId}
            onConversationsChanged={loadConversations}
            onOpenPage={setPageTarget}
            activeReference={pageTarget?.reference ? `${pageTarget.documentId}${pageTarget.reference}` : null}
            initialInput={initialInput}
            banner={banner}
            emptyState={
              <>
                <h1 className="text-2xl font-semibold tracking-tight">Wonach suchst du?</h1>
                <p className="mt-2 text-muted-foreground">
                  Ich verfolge Betriebsmittel, Klemmen und SPS-Adressen über Stromlaufplan, Stückliste, Klemmenplan, AWL-Programm und Handbücher hinweg.
                  Fragen zu einer Maschine stellst du besser auf ihrer Seite (links in der Liste): dort ist nur ihre Doku im Scope und das Modell zeigt die Bauteile.
                </p>
                <ExampleQuestions examples={EXAMPLES} onPick={setInitialInput} />
              </>
            }
          />
        </main>

        {pageTarget && <PageViewer target={pageTarget} onClose={() => setPageTarget(null)} docked />}
      </div>
    </AppShell>
  );
}
