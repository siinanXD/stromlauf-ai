import { cn } from "@/lib/utils";

/** Beleg als kleiner Chip in Mono; ohne onClick nur Anzeige (Dokument nicht aufloesbar oder kein PDF). */
export function CitationChip({
  label,
  onClick,
  active = false,
  title,
}: {
  label: string;
  onClick?: () => void;
  active?: boolean;
  title?: string;
}) {
  const style = cn(
    "mx-0.5 inline-flex max-w-full items-center border px-1.5 align-baseline font-mono text-[11.5px] leading-5 whitespace-nowrap",
    active ? "border-primary bg-primary text-primary-foreground" : "border-primary/50 bg-card text-primary",
  );
  if (!onClick) {
    return (
      <span className={cn(style, "border-border text-muted-foreground")} title={title}>
        {label}
      </span>
    );
  }
  return (
    <button type="button" className={cn(style, "hover:border-primary")} onClick={onClick} title={title}>
      {label}
    </button>
  );
}
