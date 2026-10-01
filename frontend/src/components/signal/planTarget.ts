import type { PageTarget } from "@/components/PageViewer";
import { api, factCard, type SignalMainData, type SignalMainNode } from "@/lib/api";

import { isSheetRef, nodeTitle } from "./signalColumns";

/** Geraete, Klemmen und SPS-Adressen haben ein Bauteil-Detail; Netzwerke und Variablen nicht. */
export function isPart(node: Pick<SignalMainNode, "kind">): boolean {
  return node.kind === "device" || node.kind === "terminal" || node.kind === "address";
}

/** Planseite eines Knotens mit Blattverweis ("/3.5") im Stromlaufplan der Antwort; sonst null. */
export function schematicTarget(
  node: Pick<SignalMainNode, "id" | "kind" | "ref">,
  schematic: SignalMainData["schematic"],
): PageTarget | null {
  if (!schematic || !isSheetRef(node.ref)) return null;
  const ref = node.ref.trim();
  return {
    documentId: schematic.document_id,
    filename: schematic.filename,
    reference: ref,
    label: `Stromlaufplan ${ref} · ${nodeTitle(node)}`,
    tag: node.kind === "device" ? node.id : null,
  };
}

/**
 * Wo steht ein Kennzeichen im Stromlaufplan der Quelle? Erst die Befundkarte (Blatt aus Stueckliste oder
 * Klemmenplan, sonst die Seite im Plan), sonst Seite 1 des ersten fertig gelesenen Stromlaufplans. null, wenn die
 * Quelle keinen Stromlaufplan hat. Kostet nichts: nur der Kennzeichen-Index.
 */
export async function findPlanTarget(sourceId: string, tag: string): Promise<PageTarget | null> {
  const card = await factCard(tag, [sourceId]).catch(() => null);
  const value = card?.rows
    .find((row) => row.label === "Stromlaufplan")
    ?.values.find((v) => v.document_id && v.filename?.toLowerCase().endsWith(".pdf"));
  if (card && value?.document_id && value.filename) {
    const sheet = isSheetRef(value.ref);
    return {
      documentId: value.document_id,
      filename: value.filename,
      page: value.page ?? (sheet ? undefined : 1),
      reference: sheet ? value.ref : undefined,
      label: `Stromlaufplan ${value.text} · ${card.tag}`,
      tag: card.tag,
    };
  }
  const documents = await api.listDocuments(sourceId);
  const plan = documents.find((doc) => doc.doc_type === "schematic" && doc.status === "ready");
  return plan ? { documentId: plan.id, filename: plan.filename, page: 1, pageCount: plan.page_count, label: "Stromlaufplan" } : null;
}
