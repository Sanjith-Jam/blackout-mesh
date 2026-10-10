import type { components } from './schema';

export function isWebSocketEnvelope(value: unknown): value is components['schemas']['WebSocketMessageEnvelope'];
