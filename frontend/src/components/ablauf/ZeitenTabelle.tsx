import type { Zeiten as ZeitenDaten } from "@/lib/api";
import { satz, sekunden, zeilen, zellenKlasse } from "./zeiten";

/** Dauer je Schritt über die letzten Läufe, rot über dem Zielwert. */
export function Zeiten({ zeiten }: { zeiten: ZeitenDaten }) {
  return (
    <section aria-label="Zeiten" className="space-y-3 p-4 md:px-6" data-testid="ablauf-zeiten">
      <h2 className="text-headline font-semibold">Zeiten</h2>
      <p className="text-subhead text-muted-foreground">{satz(zeiten)}</p>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-subhead">
          <caption className="sr-only">Dauer je Schritt in Sekunden</caption>
          <thead>
            <tr className="border-b border-border text-left text-footnote text-muted-foreground">
              <th scope="col" className="py-2 pr-4 font-medium">Schritt</th>
              <th scope="col" className="py-2 pr-4 font-medium">Median</th>
              <th scope="col" className="py-2 pr-4 font-medium">Letzter</th>
              <th scope="col" className="py-2 pr-4 font-medium">Langsamster</th>
              <th scope="col" className="py-2 font-medium">Ziel</th>
            </tr>
          </thead>
          <tbody>
            {zeilen(zeiten).map(({ key, label, kennzahl: k }) => (
              <tr key={key} data-testid={`zeiten-${key}`} className="border-b border-border">
                <th scope="row" className="py-2 pr-4 text-left font-medium">{label}</th>
                <td className="py-2 pr-4 font-mono font-semibold">{sekunden(k.median_s)}</td>
                <td
                  className={`py-2 pr-4 font-mono ${zellenKlasse(k.ueber_ziel)}`}
                  aria-label={k.ueber_ziel ? `${label}: ${sekunden(k.letzter_s)} über Ziel` : undefined}
                >
                  {sekunden(k.letzter_s)}
                </td>
                <td className="py-2 pr-4 font-mono">
                  {sekunden(k.max_s)}
                  {k.langsamster_trace_url && (
                    <>
                      {" "}
                      <a href={k.langsamster_trace_url} target="_blank" rel="noopener noreferrer" className="font-sans text-primary underline">
                        Langfuse
                      </a>
                    </>
                  )}
                </td>
                <td className="py-2 font-mono">{sekunden(k.ziel_s)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
