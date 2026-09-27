// Simulationskern der Ablauf-Animation. Reines JavaScript, keine Abhaengigkeiten, kein Modell.
// Liest ein MachineFlow-JSON (schemas/machine_flow.json) und fuehrt die Schrittkette aus.

export const DWELL_MS = 1500; // Wartezeit je Schritt, bevor die Simulation die Bedingungen "erfuellt"

/** Adresse oder Symbol -> IOPoint */
export function ioIndex(flow) {
  const index = new Map();
  for (const point of flow.io_points) {
    index.set(point.address, point);
    if (point.symbol) index.set(point.symbol, point);
  }
  return index;
}

/** Ruhepegel eines Eingangs: das Gegenteil von "ausgeloest" (Oeffner ruhen auf 1). */
export function restingLevel(point) {
  return point.active_state === 0 ? 1 : 0;
}

export function findStep(flow, id) {
  return flow.steps.find((s) => s.id === id) ?? null;
}

/** Anfangszustand: Eingaenge in Ruhe, Ausgaenge 0, dann Aktionen des Anfangsschritts. */
export function initialState(flow) {
  const index = ioIndex(flow);
  const inputs = {};
  const outputs = {};
  for (const point of flow.io_points) {
    if (point.direction === "DI" || point.direction === "AI") inputs[point.address] = restingLevel(point);
    else outputs[point.address] = 0;
  }
  const initial = flow.steps.find((s) => s.initial) ?? flow.steps[0] ?? null;
  const state = { stepId: initial ? initial.id : null, inputs, outputs, elapsedMs: 0, ticks: 0, log: [] };
  if (initial) applyActions(state, initial, index);
  return state;
}

function resolve(index, ref) {
  const point = index.get(ref);
  return point ? point.address : ref;
}

export function applyActions(state, step, index) {
  for (const action of step.actions) {
    const address = resolve(index, action.io);
    if (address in state.inputs) state.inputs[address] = action.state; // Aktion auf Eingang: nur Simulation
    else state.outputs[address] = action.state;
  }
}

/** true, wenn alle Bedingungen einer Transition mit den aktuellen Eingaengen erfuellt sind. */
export function satisfied(state, transition, index) {
  return transition.conditions.every((c) => {
    const address = resolve(index, c.io);
    const value = address in state.inputs ? state.inputs[address] : state.outputs[address];
    return value === c.state;
  });
}

/** Primaere Transition eines Schritts: hoechste Sicherheit, bei Gleichstand die erste. */
export function primaryTransition(step) {
  if (!step || step.transitions.length === 0) return null;
  return step.transitions.reduce((best, t) => (t.confidence > best.confidence ? t : best), step.transitions[0]);
}

/**
 * Schritt wechseln: Taster (Flanke oder Bedienelement) fallen zurueck in Ruhe, Sensoren und Sicherheitskreise
 * behalten ihren Pegel; dann Aktionen des Zielschritts ausfuehren.
 */
export function fire(flow, state, transition, index = ioIndex(flow)) {
  const from = findStep(flow, state.stepId);
  for (const c of transition.conditions) {
    const address = resolve(index, c.io);
    const point = index.get(address);
    if (point && address in state.inputs && (c.edge || point.kind === "operator")) state.inputs[address] = restingLevel(point);
  }
  const target = findStep(flow, transition.target);
  if (!target) return state;
  state.stepId = target.id;
  state.elapsedMs = 0;
  applyActions(state, target, index);
  state.log.push({ from: from ? from.id : null, to: target.id, via: transition.expression || "" });
  if (state.log.length > 200) state.log.shift();
  return state;
}

/** Eingang setzen (Klick in der DI-Tabelle); erfuellte Transition des aktuellen Schritts feuert sofort. */
export function setInput(flow, state, address, value, index = ioIndex(flow)) {
  if (!(address in state.inputs)) return state;
  state.inputs[address] = value ? 1 : 0;
  const step = findStep(flow, state.stepId);
  const ready = step ? step.transitions.find((t) => !t.timer_s && satisfied(state, t, index)) : null;
  if (ready) fire(flow, state, ready, index);
  return state;
}

/**
 * Zeitschritt. auto=true: die Simulation erfuellt nach DWELL_MS die Bedingungen der primaeren Transition
 * (Sensoren werden gelb) und feuert; Zeitglieder warten timer_s. auto=false: nur pruefen, ob eine Transition
 * durch die von Hand gesetzten Eingaenge erfuellt ist.
 */
export function tick(flow, state, dtMs, auto = true, index = ioIndex(flow)) {
  const step = findStep(flow, state.stepId);
  if (!step) return state;
  state.elapsedMs += dtMs;
  state.ticks += 1;
  const ready = step.transitions.find((t) => !t.timer_s && satisfied(state, t, index));
  if (ready) return fire(flow, state, ready, index);
  if (!auto) return state;
  const primary = primaryTransition(step);
  if (!primary) return state;
  if (primary.timer_s) {
    if (state.elapsedMs >= primary.timer_s * 1000 && satisfied(state, primary, index)) fire(flow, state, primary, index);
    return state;
  }
  if (state.elapsedMs >= DWELL_MS) {
    for (const c of primary.conditions) {
      const address = resolve(index, c.io);
      if (address in state.inputs) state.inputs[address] = c.state;
    }
    if (satisfied(state, primary, index)) fire(flow, state, primary, index);
  }
  return state;
}

/** Einzelschritt: primaere Transition sofort ausfuehren. */
export function stepOnce(flow, state, index = ioIndex(flow)) {
  const step = findStep(flow, state.stepId);
  const primary = primaryTransition(step);
  if (!primary) return state;
  for (const c of primary.conditions) {
    const address = resolve(index, c.io);
    if (address in state.inputs) state.inputs[address] = c.state;
  }
  return fire(flow, state, primary, index);
}

/** Ist der Punkt gerade "aktiv" (Aktor an, Sensor ausgeloest, Sicherheitskreis unterbrochen)? */
export function isActive(state, point) {
  const value = point.direction === "DI" || point.direction === "AI" ? state.inputs[point.address] : state.outputs[point.address];
  return value === point.active_state;
}
