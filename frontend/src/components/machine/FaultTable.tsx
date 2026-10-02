"use client";

import {
  createColumnHelper,
  createSortedRowModel,
  rowSortingFeature,
  sortFn_alphanumeric,
  sortFn_text,
  tableFeatures,
  useTable,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, Pencil, Plus, Crosshair, Stethoscope, Trash2, X } from "lucide-react";
import { useMemo } from "react";

import { Tag } from "@/components/Tag";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Fault } from "@/lib/api";

const features = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
  sortFns: { alphanumeric: sortFn_alphanumeric, text: sortFn_text },
});
const helper = createColumnHelper<typeof features, Fault>();

/** Fehlerliste der Maschine: sortierbar, filterbar nach Betriebsmittel, Tags oeffnen das Bauteil. */
export function FaultTable({
  faults,
  tagFilter,
  onTagFilter,
  onTagClick,
  onEdit,
  onDelete,
  onDiagnose,
  onShow,
  activeFaultId = null,
}: {
  faults: Fault[];
  /** Fehler markieren: Kennzeichen in Schaltschrank und Ablauf hervorheben */
  onShow?: (fault: Fault) => void;
  activeFaultId?: string | null;
  tagFilter: string | null;
  onTagFilter: (tag: string | null) => void;
  onTagClick: (tag: string) => void;
  onEdit: (fault: Fault | "new") => void;
  onDelete: (fault: Fault) => void;
  onDiagnose: (fault: Fault) => void;
}) {
  const rows = useMemo(
    () => (tagFilter ? faults.filter((f) => f.tags.some((t) => t.toUpperCase() === tagFilter.toUpperCase())) : faults),
    [faults, tagFilter],
  );

  const columns = useMemo(
    () =>
      helper.columns([
        helper.accessor("code", { header: "Code", cell: (c) => <span className="font-mono">{c.getValue()}</span> }),
        helper.accessor("symptom", { header: "Symptom" }),
        helper.accessor("cause", { header: "Ursache" }),
        helper.accessor("fix", { header: "Behebung" }),
        helper.accessor((f) => f.tags.join(" "), {
          id: "tags",
          header: "Betriebsmittel",
          cell: ({ row }) => (
            <div className="flex flex-wrap gap-x-2">
              {row.original.tags.map((tag) => (
                <Tag key={tag} value={tag} onClick={() => onTagClick(tag)} />
              ))}
            </div>
          ),
        }),
        helper.accessor("doc_ref", { header: "Quelle", cell: (c) => <span className="text-muted-foreground">{c.getValue()}</span> }),
        helper.display({
          id: "actions",
          header: "",
          cell: ({ row }) => (
            <div className="flex justify-end gap-1">
              {onShow && (
                <Button
                  size="xs"
                  variant={row.original.id === activeFaultId ? "default" : "outline"}
                  aria-pressed={row.original.id === activeFaultId}
                  onClick={() => onShow(row.original)}
                >
                  <Crosshair />
                  Zeigen
                </Button>
              )}
              <Button size="xs" variant="outline" className="border-primary/60 text-primary" onClick={() => onDiagnose(row.original)}>
                <Stethoscope />
                Diagnose
              </Button>
              <Button size="icon-xs" variant="ghost" aria-label="Bearbeiten" onClick={() => onEdit(row.original)}>
                <Pencil />
              </Button>
              <Button size="icon-xs" variant="ghost" aria-label="Löschen" className="hover:text-danger" onClick={() => onDelete(row.original)}>
                <Trash2 />
              </Button>
            </div>
          ),
        }),
      ]),
    [onDelete, onDiagnose, onEdit, onTagClick, onShow, activeFaultId],
  );

  const table = useTable({
    features,
    columns,
    data: rows,
    initialState: { sorting: [{ id: "code", desc: false }] },
    enableSortingRemoval: false,
  });

  return (
    <section className="border border-line bg-card">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <h2 className="font-mono text-sm font-semibold uppercase tracking-[0.06em]">Fehlerliste</h2>
        <span className="text-xs text-muted-foreground">
          {rows.length === faults.length ? `${faults.length} Einträge` : `${rows.length} von ${faults.length}`}
        </span>
        {tagFilter && (
          <Button size="xs" onClick={() => onTagFilter(null)}>
            Filter: {tagFilter}
            <X />
          </Button>
        )}
        <Button size="sm" variant="outline" className="ml-auto border-line" onClick={() => onEdit("new")}>
          <Plus className="size-3.5" />
          Eintrag
        </Button>
      </div>
      {faults.length === 0 ? (
        <p className="border-t border-line px-4 py-6 text-sm text-muted-foreground">
          Noch keine Einträge. Bekannte Störungen mit Ursache, Behebung und beteiligten BMK festhalten.
        </p>
      ) : (
        <Table>
          <TableHeader className="border-y border-line bg-secondary">
            {table.getHeaderGroups().map((group) => (
              <TableRow key={group.id} className="hover:bg-transparent">
                {group.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  return (
                    <TableHead key={header.id} className="font-mono text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
                      {header.column.getCanSort() ? (
                        <button className="inline-flex items-center gap-1 hover:text-foreground" onClick={header.column.getToggleSortingHandler()}>
                          <table.FlexRender header={header} />
                          {sorted === "asc" && <ArrowUp className="size-3" />}
                          {sorted === "desc" && <ArrowDown className="size-3" />}
                        </button>
                      ) : (
                        <table.FlexRender header={header} />
                      )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id} className="align-top">
                {row.getAllCells().map((cell) => (
                  <TableCell key={cell.id} className="whitespace-normal text-[13px]">
                    <table.FlexRender cell={cell} />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
