import type { WhyData, WhyInput } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";

import { buildWhyTree, type WhyNode } from "./whyTree";

function InputRow({ input, writers, onOpenDetail }: { input: WhyInput; writers: WhyNode[]; onOpenDetail: (detail: DetailRef) => void }) {
  const linkClass = "min-h-11 rounded-md px-2 font-mono text-[13px] text-primary underline-offset-2 hover:underline";
  return (
    <li data-why-input={input.id} className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-x-2">
        <span className="text-sm">{input.label}</span>
        {input.terminal && (
          <button type="button" className={linkClass} onClick={() => onOpenDetail({ kind: "signal", tag: input.terminal! })}>
            {input.terminal}
          </button>
        )}
        {input.device && (
          <button type="button" className={linkClass} onClick={() => onOpenDetail({ kind: "part", tag: input.device! })}>
            {input.device}
          </button>
        )}
        {!input.terminal && !input.device && input.written_by.length === 0 && (
          <span className="text-footnote text-muted-foreground">Keine Klemme im Plan gefunden</span>
        )}
      </div>
      {writers.length > 0 && (
        <ul className="ml-3 flex flex-col gap-2 border-l border-border pl-3" aria-label={`Netzwerke, die ${input.label} schreiben`}>
          {writers.map((w) => (
            <NetworkItem key={w.network.id} node={w} onOpenDetail={onOpenDetail} />
          ))}
        </ul>
      )}
    </li>
  );
}

function NetworkItem({ node, onOpenDetail }: { node: WhyNode; onOpenDetail: (detail: DetailRef) => void }) {
  const { network, inputs } = node;
  return (
    <li data-why-network={network.id} className="flex flex-col gap-1">
      <p className="text-sm font-semibold">
        {network.ref}
        {network.title ? <span className="font-normal text-muted-foreground">{` · ${network.title}`}</span> : null}
      </p>
      {network.klartext.length > 0 && (
        <p className="text-footnote text-muted-foreground">{network.klartext.join(" ")}</p>
      )}
      {inputs.length > 0 && (
        <ul className="flex flex-col gap-1" aria-label={`Eingänge von ${network.ref}`}>
          {inputs.map(({ input, writers }) => (
            <InputRow key={input.id} input={input} writers={writers} onOpenDetail={onOpenDetail} />
          ))}
        </ul>
      )}
    </li>
  );
}

/** Bedingungsbaum zu "Warum kommt … nicht?": Ausgang, schreibende Netzwerke, Eingaenge mit Klemme und Betriebsmittel. */
export function WhyTree({ data, onOpenDetail }: { data: WhyData; onOpenDetail: (detail: DetailRef) => void }) {
  const tree = buildWhyTree(data);
  const { target } = data;
  return (
    <div data-testid="why-tree" className="flex flex-col gap-2">
      <p className="text-sm">
        <span className="text-muted-foreground">Ausgang </span>
        <span className="font-semibold">{target.label}</span>
        {target.terminal && (
          <button type="button" className="ml-2 min-h-11 rounded-md px-2 font-mono text-[13px] text-primary underline-offset-2 hover:underline" onClick={() => onOpenDetail({ kind: "signal", tag: target.terminal! })}>
            {target.terminal}
          </button>
        )}
        {target.device && (
          <button type="button" className="min-h-11 rounded-md px-2 font-mono text-[13px] text-primary underline-offset-2 hover:underline" onClick={() => onOpenDetail({ kind: "part", tag: target.device! })}>
            {target.device}
          </button>
        )}
      </p>
      <ul className="flex flex-col gap-3" aria-label="Netzwerke, die den Ausgang schreiben">
        {tree.map((n) => (
          <NetworkItem key={n.network.id} node={n} onOpenDetail={onOpenDetail} />
        ))}
      </ul>
    </div>
  );
}
