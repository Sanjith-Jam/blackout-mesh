import { vi } from 'vitest';

type Handler = (body: unknown) => { status?: number; json: unknown } | Promise<{ status?: number; json: unknown }>;

/** Minimal fetch mock keyed by "METHOD /path". Records every call for assertions. */
export function mockFetch(routes: Record<string, Handler>) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    const method = (init?.method ?? 'GET').toUpperCase();
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path: url.pathname, body });
    const handler = routes[`${method} ${url.pathname}`];
    if (!handler) return new Response('not mocked', { status: 404 });
    const { status = 200, json } = await handler(body);
    return new Response(JSON.stringify(json), { status, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fn);
  return { fn, calls, posts: () => calls.filter(c => c.method === 'POST') };
}

/** Controllable WebSocket stand-in that records instances. */
export class FakeSocket {
  static instances: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;
  constructor(public url: string) { FakeSocket.instances.push(this); }
  close() { this.closed = true; this.onclose?.(); }
  send() {}
  open() { this.onopen?.(); }
  message(data: unknown) { this.onmessage?.({ data: typeof data === 'string' ? data : JSON.stringify(data) }); }
  drop() { this.onclose?.(); }
}

export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}
