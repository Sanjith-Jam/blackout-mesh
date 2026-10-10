/** Electrical relationships used by the Electrical Laws section. SI units throughout: volts (V), amperes (A),
 * ohms (Ω), watts (W), seconds (s). Every function rejects inputs where the relationship is undefined
 * (division by zero, negative resistance, power factor outside 0–1) by returning null, never a made-up value. */

const finite = (...xs: number[]) => xs.every(x => Number.isFinite(x));

/** Ohm's law, V = I × R, for an ideal linear resistor (DC, or AC with a purely resistive load). */
export function ohmVoltage(currentA: number, resistanceOhm: number): number | null {
  if (!finite(currentA, resistanceOhm) || resistanceOhm < 0) return null;
  return currentA * resistanceOhm;
}

export function ohmCurrent(voltageV: number, resistanceOhm: number): number | null {
  if (!finite(voltageV, resistanceOhm) || resistanceOhm <= 0) return null;
  return voltageV / resistanceOhm;
}

export function ohmResistance(voltageV: number, currentA: number): number | null {
  if (!finite(voltageV, currentA) || currentA === 0) return null;
  const r = voltageV / currentA;
  return r < 0 ? null : r;
}

/** DC (or purely resistive) power. The three forms agree whenever V = I × R holds. */
export const powerVI = (voltageV: number, currentA: number) => (finite(voltageV, currentA) ? voltageV * currentA : null);
export const powerI2R = (currentA: number, resistanceOhm: number) =>
  (finite(currentA, resistanceOhm) && resistanceOhm >= 0 ? currentA * currentA * resistanceOhm : null);
export const powerV2R = (voltageV: number, resistanceOhm: number) =>
  (finite(voltageV, resistanceOhm) && resistanceOhm > 0 ? (voltageV * voltageV) / resistanceOhm : null);

/** Single-phase AC real power with RMS quantities: P = V × I × PF. */
export function singlePhaseRealPower(voltageRmsV: number, currentRmsA: number, powerFactor: number): number | null {
  if (!finite(voltageRmsV, currentRmsA, powerFactor) || powerFactor < 0 || powerFactor > 1) return null;
  return voltageRmsV * currentRmsA * powerFactor;
}

/** Balanced three-phase real power with line-to-line voltage and line current: P = √3 × V_L × I_L × PF. */
export function threePhaseRealPower(lineVoltageV: number, lineCurrentA: number, powerFactor: number): number | null {
  if (!finite(lineVoltageV, lineCurrentA, powerFactor) || powerFactor < 0 || powerFactor > 1) return null;
  return Math.sqrt(3) * lineVoltageV * lineCurrentA * powerFactor;
}

/** Single-phase RMS current drawn for a real power at a voltage and power factor: I = P / (V × PF). */
export function singlePhaseCurrent(powerW: number, voltageRmsV: number, powerFactor: number): number | null {
  if (!finite(powerW, voltageRmsV, powerFactor) || voltageRmsV <= 0 || powerFactor <= 0 || powerFactor > 1) return null;
  return powerW / (voltageRmsV * powerFactor);
}

/** Kirchhoff's current law at one node: the signed sum of currents is zero. Returns the residual (A). */
export function kclResidual(enteringA: number[], leavingA: number[]): number {
  return enteringA.reduce((a, b) => a + b, 0) - leavingA.reduce((a, b) => a + b, 0);
}

/** Kirchhoff's voltage law around one loop with series resistors: the source voltage equals the sum of drops.
 * Returns the loop current and each drop, or null if the loop has no resistance. */
export function seriesLoop(sourceV: number, resistancesOhm: number[]): { currentA: number; dropsV: number[]; residualV: number } | null {
  const total = resistancesOhm.reduce((a, b) => a + b, 0);
  if (!finite(sourceV, ...resistancesOhm) || resistancesOhm.some(r => r < 0) || total <= 0) return null;
  const currentA = sourceV / total;
  const dropsV = resistancesOhm.map(r => currentA * r);
  return { currentA, dropsV, residualV: sourceV - dropsV.reduce((a, b) => a + b, 0) };
}

/** Energy E = P × t. Returns watt-hours, kilowatt-hours and joules for a power held over hours. */
export function energy(powerW: number, hours: number): { wh: number; kwh: number; joules: number } | null {
  if (!finite(powerW, hours) || powerW < 0 || hours < 0) return null;
  const wh = powerW * hours;
  return { wh, kwh: wh / 1000, joules: wh * 3600 };
}

/** Demand against a capacity limit: whether the request exceeds it, and by how much. */
export function capacityBalance(requestedW: number, limitW: number, servedW: number) {
  return { exceeded: requestedW > limitW, deficitW: Math.max(0, requestedW - limitW),
           headroomW: Math.max(0, limitW - servedW), unservedW: Math.max(0, requestedW - servedW),
           utilisation: limitW > 0 ? servedW / limitW : null };
}

export const fmtW = (w: number) => `${Math.round(w).toLocaleString('en-US')} W`;
export const fmt = (x: number | null | undefined, digits = 2) =>
  x == null || !Number.isFinite(x) ? '—' : Number(x.toFixed(digits)).toLocaleString('en-US', { maximumFractionDigits: digits });
