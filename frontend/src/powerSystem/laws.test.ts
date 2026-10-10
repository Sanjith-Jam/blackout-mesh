import { describe, expect, it } from 'vitest';
import { capacityBalance, energy, kclResidual, ohmCurrent, ohmResistance, ohmVoltage, powerI2R, powerV2R, powerVI,
  seriesLoop, singlePhaseCurrent, singlePhaseRealPower, threePhaseRealPower } from './laws';

describe('electrical laws', () => {
  it("Ohm's law solves for each quantity and refuses undefined cases", () => {
    expect(ohmVoltage(2, 115)).toBe(230);
    expect(ohmCurrent(230, 115)).toBe(2);
    expect(ohmResistance(230, 2)).toBe(115);
    expect(ohmCurrent(230, 0)).toBeNull();
    expect(ohmResistance(230, 0)).toBeNull();
    expect(ohmVoltage(1, -5)).toBeNull();
  });

  it('the three DC power forms agree when V = I × R', () => {
    const v = 12, r = 6, i = ohmCurrent(v, r)!;
    expect(powerVI(v, i)).toBeCloseTo(24);
    expect(powerI2R(i, r)).toBeCloseTo(24);
    expect(powerV2R(v, r)).toBeCloseTo(24);
  });

  it('single-phase and balanced three-phase real power use the right forms', () => {
    expect(singlePhaseRealPower(230, 10, 0.9)).toBeCloseTo(2070);
    expect(threePhaseRealPower(400, 10, 0.9)).toBeCloseTo(Math.sqrt(3) * 3600);
    expect(singlePhaseRealPower(230, 10, 1.2)).toBeNull();
    expect(singlePhaseCurrent(2300, 230, 1)).toBeCloseTo(10);
    expect(singlePhaseCurrent(2300, 230, 0)).toBeNull();
  });

  it("Kirchhoff's laws balance", () => {
    expect(kclResidual([10], [4, 3.5, 2.5])).toBeCloseTo(0);
    const loop = seriesLoop(24, [4, 8])!;
    expect(loop.currentA).toBeCloseTo(2);
    expect(loop.dropsV).toEqual([8, 16]);
    expect(loop.residualV).toBeCloseTo(0);
    expect(seriesLoop(24, [0, 0])).toBeNull();
  });

  it('energy conversions are explicit', () => {
    expect(energy(300, 2)).toEqual({ wh: 600, kwh: 0.6, joules: 2_160_000 });
    expect(energy(-1, 2)).toBeNull();
  });

  it('capacity balance reports deficit only when the request exceeds the limit', () => {
    expect(capacityBalance(14000, 6000, 6000)).toMatchObject({ exceeded: true, deficitW: 8000, headroomW: 0, unservedW: 8000 });
    expect(capacityBalance(6000, 6000, 6000)).toMatchObject({ exceeded: false, deficitW: 0 });
  });
});
