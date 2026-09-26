import type { Node } from "@xyflow/react";

import type { Layout, LayoutPart, LayoutPartInput } from "@/lib/api";

/** Pixel pro mm bei Zoom 1: 6000 mm Band = 900 px. */
export const MM_TO_PX = 0.15;
/** Raster im Canvas: fein 100 mm, grob 1000 mm. */
export const GRID_MINOR_MM = 100;
export const GRID_MAJOR_MM = 1000;
/** Neues Teil aus der Werkzeugleiste. */
export const NEW_PART_MM = 300;

export type ResizeBox = { x: number; y: number; width: number; height: number };
export type PartNodeData = { part: LayoutPart; onResizeEnd?: (partId: string, box: ResizeBox) => void };
export type FloorNodeData = { width_mm: number; depth_mm: number };
export type PartNode = Node<PartNodeData, "part">;
export type FloorNode = Node<FloorNodeData, "floor">;
export type CanvasNode = PartNode | FloorNode;

export const FLOOR_ID = "__floor__";

/** Flaechige Teile liegen unten, damit Geraete darauf klickbar bleiben. */
const BACKGROUND_KINDS = new Set(["Band/Förderer", "Rahmen", "Schaltschrank"]);

export const px = (mm: number) => mm * MM_TO_PX;
export const mm = (pixels: number) => Math.round((pixels / MM_TO_PX) * 10) / 10;

export function partToNode(part: LayoutPart, selected: boolean, onResizeEnd?: PartNodeData["onResizeEnd"]): PartNode {
  return {
    id: part.id,
    type: "part",
    position: { x: px(part.x_mm), y: px(part.y_mm) },
    width: px(part.w_mm),
    height: px(part.h_mm),
    data: { part, onResizeEnd },
    selected,
    zIndex: BACKGROUND_KINDS.has(part.kind) ? 1 : 2,
  };
}

export function floorNode(layout: Layout): FloorNode {
  return {
    id: FLOOR_ID,
    type: "floor",
    position: { x: 0, y: 0 },
    width: px(layout.width_mm || 1000),
    height: px(layout.depth_mm || 1000),
    data: { width_mm: layout.width_mm, depth_mm: layout.depth_mm },
    draggable: false,
    selectable: false,
    deletable: false,
    // React Flow faengt sonst jeden Klick auf der Grundflaeche ab (onNodeClick) -> Zeichnen/Abwaehlen ginge nicht
    style: { pointerEvents: "none" },
    zIndex: 0,
  };
}

export function nodeToPatch(node: { position: { x: number; y: number }; width?: number; height?: number }): Partial<LayoutPartInput> {
  const patch: Partial<LayoutPartInput> = { x_mm: mm(node.position.x), y_mm: mm(node.position.y) };
  if (node.width) patch.w_mm = mm(node.width);
  if (node.height) patch.h_mm = mm(node.height);
  return patch;
}

export function formatMm(value: number) {
  return `${Math.round(value).toLocaleString("de-DE")}`;
}
