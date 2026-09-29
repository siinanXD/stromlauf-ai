import { cn } from "@/lib/utils";

/** Beleg als kleiner Chip in Mono; ohne onClick nur Anzeige (Dokument nicht aufloesbar oder kein PDF).
 * invalid: der Zitat-Resolver hat den Ort nicht in den Fundstellen gefunden - gestrichelter Rahmen, Kreuz,
 * Grund als sr-only-Text (Screenreader, Tastatur) und im title (Maus). Rot bleibt Fehlern vorbehalten. */
export function CitationChip({
  label,
  onClick,
  active = false,
  title,
  invalid = false,
}: {
  label: string;
  onClick?: () => void;
  active?: boolean;
  title?: string;
  invalid?: boolean;
}) {
  const tone = active
    ? "border-primary bg-primary text-primary-foreground"
    : onClick
      ? "border-primary/50 bg-card text-primary hover:border-primary"
      : "border-border bg-card text-muted-foreground";
  const style = cn(
    "mx-0.5 inline-flex max-w-full items-center gap-1 border px-1.5 align-baseline font-mono text-[11.5px] leading-5 whitespace-nowrap",
    tone,
    invalid && "border-dashed",
    invalid && !active && "border-muted-foreground text-muted-foreground",
  );
  const content = (
    <>
      {invalid && <span aria-hidden="true">✕</span>}
      {label}
      {invalid && <span className="sr-only">, Beleg ungültig{title ? `: ${title}` : ""}</span>}
    </>
  );
  if (!onClick) {
    return (
      <span className={style} title={title} data-invalid={invalid || undefined}>
        {content}
      </span>
    );
  }
  return (
    <button type="button" className={style} onClick={onClick} title={title} data-invalid={invalid || undefined}>
      {content}
    </button>
  );
}
