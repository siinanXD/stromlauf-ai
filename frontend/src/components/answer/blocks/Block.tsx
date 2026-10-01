"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { useInView } from "../useInView";

export type BlockKind = "faults" | "text" | "parts" | "signal" | "plan" | "cabinet" | "citations";

/**
 * Rahmen eines Antwortblocks: Titel und Quelle stehen immer da, damit jeder Block sagt, woher er kommt
 * ("Fehlerliste", "Blatt 3"). Grau ist der Normalzustand; Farbe nur an Bedienelementen.
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
    <section ref={innerRef} data-block={kind} data-testid={testId} aria-label={title} className={cn("rounded-lg border border-border bg-card", className)}>
      <header className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 px-3 pt-2.5">
        <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">{title}</h3>
        {source && <span className="min-w-0 truncate text-[11px] text-muted-foreground">· {source}</span>}
        {action && <span className="ml-auto">{action}</span>}
      </header>
      <div className="px-3 pb-3 pt-2">{children}</div>
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
            <div key={i} className="aspect-[4/3] w-40 shrink-0 animate-pulse rounded-lg bg-secondary" />
          ))}
        </div>
      ) : (
        Array.from({ length: rows }, (_, i) => <div key={i} aria-hidden className={cn("h-4 animate-pulse rounded bg-secondary", i % 2 ? "w-2/3" : "w-full")} />)
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
