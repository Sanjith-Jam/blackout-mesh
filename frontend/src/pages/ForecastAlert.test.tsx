import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { DemandForecast } from '../types';
import { ForecastAlert } from './DemandForecastPanel';

const forecast = (status: string) => ({ status, first_shortage_s: 40, capacity_w: 6000, observations_w: [4400, 4750],
  points: [{ ahead_s: 60, demand_w: 6540, lower_w: 6242, upper_w: 6838 }] } as unknown as DemandForecast);

describe('forecast early warning', () => {
  it('appears only for shortage risk and stays advisory', () => {
    const { rerender } = render(<ForecastAlert forecast={forecast('SHORTAGE_RISK')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('possible shortfall within 40 s');
    expect(screen.getByRole('alert')).toHaveTextContent('Advisory; trained on synthetic data');
    rerender(<ForecastAlert forecast={forecast('OK')} />);
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
