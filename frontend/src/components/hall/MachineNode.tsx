"use client";

import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { AlertTriangle, Archive, Bot, Box, Cog, FileText, LayoutGrid, MoveRight, Package } from "lucide-react";
import Link from "next/link";
import type { ComponentType } from "react";

import { MACHINE_TYPE_LABELS, type Machine, type MachineType } from "@/lib/api";
import { TILE } from "@/lib/site";
import { cn } from "@/lib/utils";

export const TILE_W = TILE.w;
export const TILE_H = TILE.h;

const TYPE_ICON: Record<MachineType, ComponentType<{ className?: string }>> = {
  conveyor: MoveRight,
  main: Cog,
  packaging: Package,
  robot: Bot,
  storage: Archive,
  other: Box,
};

export type MachineNodeData = { machine: Machine };
export type MachineNodeType = Node<MachineNodeData, "machine">;

const HANDLE = "!size-2.5 !rounded-none !border-primary !bg-card opacity-0 transition-opacity group-hover:opacity-100";

/** Maschinenkachel in der Halle: Typ, Name, Kennzahlen; Griffe links/rechts fuer den Materialfluss. */
export function MachineNode({ data, selected }: NodeProps<MachineNodeType>) {
  const { machine } = data;
  const Icon = TYPE_ICON[machine.machine_type] ?? Box;
  return (
    <div
      className={cn(
        "group flex size-full flex-col border bg-card px-3 py-2.5",
        selected ? "border-2 border-primary" : "border-line hover:border-primary",
      )}
    >
      <Handle type="target" position={Position.Left} className={HANDLE} />
      <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <Icon className="size-3.5" />
        <span className="truncate">{MACHINE_TYPE_LABELS[machine.machine_type] ?? machine.machine_type}</span>
      </div>
      <div className="mt-1 truncate font-mono text-[13px] font-semibold uppercase" title={machine.name}>
        {machine.name}
      </div>
      {machine.key_figure && (
        <div className="truncate font-mono text-[11px] text-muted-foreground" title="Erste Kennzahl">
          {machine.key_figure}
        </div>
      )}
      <div className="mt-auto flex items-center gap-2.5 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-0.5" title="Dokumente">
          <FileText className="size-3" />
          {machine.document_count}
        </span>
        <span className={cn("flex items-center gap-0.5", machine.fault_count > 0 && "text-danger")} title="Fehlereinträge">
          <AlertTriangle className="size-3" />
          {machine.fault_count}
        </span>
        <span className="flex items-center gap-0.5" title="Schaltschrankbilder">
          <LayoutGrid className="size-3" />
          {machine.cabinet_count}
        </span>
        <Link
          href={`/werk/maschine/${machine.id}`}
          onClick={(event) => event.stopPropagation()}
          className="nodrag ml-auto text-primary hover:underline"
        >
          öffnen
        </Link>
      </div>
      <Handle type="source" position={Position.Right} className={HANDLE} />
    </div>
  );
}
