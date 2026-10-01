"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { useInView } from "../useInView";

export type BlockKind = "faults" | "text" | "parts" | "signal" | "plan" | "cabinet" | "citations";

/**
 * Rahmen eines Antwortblocks (Figma "Block-Karte"): weisse Karte, 16 px Radius, Kartenschatten; im Kopf Titel in
 * Grossbuchstaben und rechts die Quelle, damit jeder Block sagt, woher er kommt ("Fehlerliste", "Blatt 3").
 * Grau ist der Normalzustand; Farbe nur an Bedienelementen.
 */
export function Block({
  kind,
  title,
  source,
  action,
  children,
  className,
  testId,
  innerRef,
}: {
  kind: BlockKind;
  title: string;
  source?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
  innerRef?: (node: HTMLElement | null) => void;
}) {
  return (
    <section ref={innerRef} data-block={kind} data-testid={testId} aria-label={title} className={cn("rounded-lg bg-card px-4 py-3 shadow-card", className)}>
      <header className="flex min-h-[18px] items-center gap-2 text-footnote">
        <h3 className="shrink-0 font-semibold text-muted-foreground uppercase">{title}</h3>
        {source && (
          <span className="min-w-0 flex-1 truncate text-right text-muted-foreground">
            <span className="sr-only">Quelle: </span>
            {source}
          </span>
        )}
        {action && <span className={cn("-my-3 shrink-0", !source && "ml-auto")}>{action}</span>}
      </header>
      <div className="pt-2">{children}</div>
    </section>
  );
}

/** Platzhalter in Blockform, solange Daten laden oder der Block noch nicht im Bild war. */
export function BlockSkeleton({ rows = 2, tiles = 0, label = "Lädt …" }: { rows?: number; tiles?: number; label?: string }) {
  return (
    <div className="space-y-2" aria-busy="true">
      <span className="sr-only">{label}</span>
      {tiles > 0 ? (
        <div className="flex gap-3" aria-hidden>
          {Array.from({ length: tiles }, (_, i) => (
            <div key={i} className="h-[184px] w-[min(326px,80%)] shrink-0 animate-pulse rounded-md bg-bg-fill" />
          ))}
        </div>
      ) : (
        Array.from({ length: rows }, (_, i) => <div key={i} aria-hidden className={cn("h-4 animate-pulse rounded-xs bg-bg-fill", i % 2 ? "w-2/3" : "w-full")} />)
      )}
    </div>
  );
}

/** Block, dessen Inhalt erst geladen wird, wenn er ins Bild kommt. */
export function LazyBlock({
  skeleton,
  children,
  ...block
}: Omit<Parameters<typeof Block>[0], "children" | "innerRef"> & { skeleton: ReactNode; children: () => ReactNode }) {
  const [ref, inView] = useInView<HTMLElement>();
  return (
    <Block {...block} innerRef={ref}>
      {inView ? children() : skeleton}
    </Block>
  );
}
