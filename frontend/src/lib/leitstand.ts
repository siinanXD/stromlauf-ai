/** Zustand des Werks zu einer Uhrzeit, abgeleitet aus den Intervallen der Simulation (ohne Nachrechnen). */

import type { SimResult, SimResourceKind } from "./api";

export interface ResourceState {
  key: string;
  label: string;
  kind: SimResourceKind;
  capacity: number;
  busy: { slot: number; order: string; stage: string; progress: number }[];
  queue: string[];
  hold: string[];
}

export interface LeitstandState {
  resources: Record<string, ResourceState>;
  stock: { code: string; name: string; units: number; pallets: number }[];
  docks: ({ order: string; truck: number; progress: number } | null)[];
  waitingTrucks: number;
  todayOut: { order: string; trucks: number }[];
  orders: Record<string, { status: string; done: boolean; waiting: boolean }>;
  closed: { office: boolean; shipping: boolean };
}

const ms = (iso: string) => new Date(iso).getTime();
const sameDay = (a: number, b: number) => new Date(a).toDateString() === new Date(b).toDateString();
const inside = (t: number, start: string, end: string) => ms(start) <= t && t < ms(end);

export function stateAt(result: SimResult, t: number): LeitstandState {
  const labels = Object.fromEntries(result.resources.map((r) => [r.key, r.label]));
  const resources: Record<string, ResourceState> = Object.fromEntries(
    result.resources.map((r) => [r.key, { ...r, busy: [], queue: [], hold: [] }]),
  );
  const dockCount = result.resources.find((r) => r.kind === "dock")?.capacity ?? 0;
  const docks: LeitstandState["docks"] = Array.from({ length: dockCount }, () => null);
  const orders: LeitstandState["orders"] = {};
  const today = new Map<string, number>();
  let waitingTrucks = 0;

  for (const order of result.orders) {
    let status = "";
    let waiting = false;
    for (const stage of order.stages) {
      const active = inside(t, stage.start, stage.end);
      const queued = inside(t, stage.arrive, stage.start);
      const label = stage.stage === "credit" ? "Kreditklärung" : stage.stage === "ship" ? "Verladung" : (labels[stage.resource] ?? stage.label);
      if (active) status = label;
      else if (queued && !status) {
        status = `wartet ${label}`;
        waiting = true;
      }
      if (stage.stage === "credit") {
        if (active) resources["office:fin"]?.hold.push(order.number);
        continue;
      }
      const resource = resources[stage.resource];
      if (!resource || resource.kind === "dock") continue;
      if (active) {
        const progress = (t - ms(stage.start)) / Math.max(1, ms(stage.end) - ms(stage.start));
        resource.busy.push({ slot: stage.slot ?? 0, order: order.number, stage: stage.stage, progress });
      } else if (queued) resource.queue.push(order.number);
    }
    const ship = order.stages.find((s) => s.stage === "ship");
    for (const truck of order.trucks) {
      if (inside(t, truck.start, truck.end)) {
        docks[truck.dock - 1] = { order: order.number, truck: truck.truck, progress: (t - ms(truck.start)) / (ms(truck.end) - ms(truck.start)) };
      } else if (ship && ms(ship.arrive) <= t && t < ms(truck.start)) waitingTrucks += 1;
      if (sameDay(ms(truck.start), t)) today.set(order.number, (today.get(order.number) ?? 0) + 1);
    }
    const done = !!order.shipped_at && ms(order.shipped_at) <= t;
    if (t < ms(order.received_at)) status = "noch nicht eingegangen";
    else if (done) status = "verladen";
    else if (!status) status = "bereit";
    orders[order.number] = { status, done, waiting };
  }

  const stock = Object.entries(result.stock).map(([code, item]) => {
    const point = [...item.points].reverse().find(([time]) => ms(time) <= t);
    const units = point ? point[1] : (item.points[0]?.[1] ?? 0);
    return { code, name: item.name, units, pallets: units / item.units_per_pallet };
  });
  const closedAt = (spans: [string, string][] = []) => spans.some(([a, b]) => inside(t, a, b));

  return {
    resources,
    stock,
    docks,
    waitingTrucks,
    todayOut: [...today].map(([order, trucks]) => ({ order, trucks })),
    orders,
    closed: { office: closedAt(result.closed.office), shipping: closedAt(result.closed.shipping) },
  };
}
