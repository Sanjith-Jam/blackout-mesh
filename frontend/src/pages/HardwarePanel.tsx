import { useState } from 'react';
import { connectHardware, disconnectHardware } from '../api';
import { HardwareStatus } from '../types';

const ROOMS: [string, number][] = [['A', 3], ['B', 4], ['C', 5]];
const bit = (mask: number | null | undefined, b: number) => mask != null && ((mask >> b) & 1) === 1;

const LINK_TEXT: Record<string, string> = {
  NOT_CONFIGURED: 'Not connected',
  CONNECTING: 'Waiting for board A…',
  SYNCING: 'Synchronising with board A…',
  CONNECTED: 'Connected',
  STALE: 'Connection stale',
};

/** Physical boards: board A (reader + buttons) and board B (LEDs), as reported by the gateway bridge. */
export default function HardwarePanel({ hardware }: { hardware?: HardwareStatus }) {
  const [port, setPort] = useState('COM4');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hw = hardware ?? { link: 'NOT_CONFIGURED', commanded_mask: null, confirmed_mask: null };
  const configured = hw.link !== 'NOT_CONFIGURED';
  const confirmedFresh = hw.link === 'CONNECTED' && hw.led_confirmed === true;

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); }
    finally { setBusy(false); }
  };

  return <section className="hardware-panel" aria-labelledby="hardware-title">
    <h3 id="hardware-title">Physical boards</h3>
    <p className={`hardware-panel__link is-${hw.link.toLowerCase()}`} role="status">{LINK_TEXT[hw.link] ?? hw.link}</p>
    {configured ? <>
      <dl className="hardware-panel__facts">
        <div><dt>Card reader</dt><dd>{hw.board_a?.reader_ok == null ? '—' : hw.board_a.reader_ok ? 'OK' : 'FAULT: use the fallback button'}</dd></div>
        <div><dt>Board B</dt><dd>{hw.board_b?.online ? (hw.board_b.radio_ready ? 'Online, bound' : 'Online, binding') : 'Not heard'}</dd></div>
      </dl>
      <div className="hardware-panel__leds" aria-label="Board B room LEDs">
        {ROOMS.map(([room, b]) => {
          const commanded = bit(hw.commanded_mask, b);
          const confirmed = bit(hw.confirmed_mask, b);
          const state = !confirmedFresh ? 'unknown' : confirmed ? 'on' : 'off';
          return <span key={room} className={`hardware-panel__led is-${state}`}
                       title={`Room ${room}: commanded ${hw.commanded_mask == null ? 'unknown' : commanded ? 'ON' : 'OFF'}, board B confirmed ${!confirmedFresh ? 'nothing current' : confirmed ? 'ON' : 'OFF'}`}>
            <i />{room} <b>{state === 'unknown' ? '?' : state.toUpperCase()}</b>
          </span>;
        })}
      </div>
      <p className="hardware-panel__note">{confirmedFresh ? 'LEDs confirmed by board B.' : 'Waiting for board B to confirm the latest command.'}</p>
      {hw.recent_events && hw.recent_events.length > 0 && <p className="hardware-panel__note">Last input: {hw.recent_events[hw.recent_events.length - 1].action.replace(/_/g, ' ').toLowerCase()}{hw.recent_events[hw.recent_events.length - 1].room ? ` (room ${hw.recent_events[hw.recent_events.length - 1].room})` : ''}</p>}
      <button className="classroom-demo__button" disabled={busy} onClick={() => void run(disconnectHardware)}>Disconnect board A</button>
    </> : <>
      <p className="hardware-panel__note">Plug board A in by USB, enter its port and connect.</p>
      <div className="hardware-panel__connect">
        <label htmlFor="gateway-port">Board A port</label>
        <input id="gateway-port" value={port} onChange={e => setPort(e.target.value)} />
        <button className="classroom-demo__button" disabled={busy || !port.trim()} onClick={() => void run(() => connectHardware(port.trim()))}>Connect</button>
      </div>
    </>}
    {(error || hw.port_error) && <p className="hardware-panel__error" role="alert">{error ?? hw.port_error}</p>}
  </section>;
}
