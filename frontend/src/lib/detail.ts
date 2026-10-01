import type { PageTarget } from "@/components/PageViewer";

/** Was die Detailspalte (PC) bzw. die Detail-Ebene (Handy) gerade zeigt. Steht als ?detail= in der URL. */
export type DetailRef =
  | { kind: "signal"; tag: string }
  | { kind: "plan"; target: PageTarget }
  | { kind: "part"; tag: string }
  | { kind: "cabinet"; cabinetId: string; hotspotId?: string }
  | { kind: "fault"; faultId: string };

/** URL-tauglich und stabil: dieselbe Detailansicht ergibt immer denselben Parameter. */
export function detailToParam(detail: DetailRef): string {
  return encodeURIComponent(JSON.stringify(detail));
}

export function detailFromParam(param: string | null): DetailRef | null {
  if (!param) return null;
  try {
    const value = JSON.parse(decodeURIComponent(param));
    switch (value?.kind) {
      case "signal":
      case "part":
        return typeof value.tag === "string" ? value : null;
      case "plan":
        return typeof value.target?.documentId === "string" ? value : null;
      case "cabinet":
        return typeof value.cabinetId === "string" ? value : null;
      case "fault":
        return typeof value.faultId === "string" ? value : null;
      default:
        return null;
    }
  } catch {
    return null;
  }
}
