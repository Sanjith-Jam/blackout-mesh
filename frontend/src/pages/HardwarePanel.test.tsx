import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import HardwarePanel from './HardwarePanel';

test('stale hardware cannot present a previous mask as current LED confirmation', () => {
  const { rerender } = render(<HardwarePanel hardware={{ link: 'CONNECTED', commanded_mask: 8, confirmed_mask: 8, led_confirmed: true }} />);
  expect(screen.getByText('LEDs confirmed by board B.')).toBeVisible();
  rerender(<HardwarePanel hardware={{ link: 'STALE', commanded_mask: 8, confirmed_mask: 8, led_confirmed: true }} />);
  expect(screen.queryByText('LEDs confirmed by board B.')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Board B room LEDs').querySelectorAll('.is-unknown')).toHaveLength(3);
});
