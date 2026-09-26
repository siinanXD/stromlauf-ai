import { cn } from "@/lib/utils";

/** Betriebsmittelkennzeichen, Klemme oder SPS-Adresse: ueberall gleich in Mono und Akzentfarbe. */
export function Tag({ value, onClick, className }: { value: string; onClick?: () => void; className?: string }) {
  const style = cn("font-mono text-primary", className);
  if (!onClick) return <span className={style}>{value}</span>;
  return (
    <button type="button" onClick={onClick} className={cn(style, "hover:underline")}>
      {value}
    </button>
  );
}
