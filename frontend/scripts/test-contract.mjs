import assert from 'node:assert/strict';
import { isWebSocketEnvelope } from '../src/runtime-contract.js';

const valid = {
  type: 'snapshot', sent_at: '2026-10-10T00:00:00Z',
  payload: {
    contract: { identity: { site_id: 'campus', run_id: 'run-1', server_epoch: 1, state_revision: 2,
      config_hash: 'hash', catalog_version: 'catalog-v1', policy_version: 'policy-v1', model_version: 'model-v1',
      observation_time: '2026-10-10T00:00:00Z' } },
    control_revision: 2, published_revision: 2, generated_at: '2026-10-10T00:00:00Z',
    services: [{ id: 'L1', name: 'Lighting', tier: 'T1', feeder: 'A', watts: 100, requested: true, modeled_served: true }],
    source: { capacity_w: 1000 },
  },
};

assert.equal(isWebSocketEnvelope(valid), true);
assert.equal(isWebSocketEnvelope({ ...valid, type: 'command' }), false);
assert.equal(isWebSocketEnvelope({ ...valid, sent_at: 'yesterday' }), false);
assert.equal(isWebSocketEnvelope({ ...valid, payload: { ...valid.payload, contract: {} } }), false);
assert.equal(isWebSocketEnvelope({ ...valid, payload: { ...valid.payload, source: { capacity_w: '1000' } } }), false);
assert.equal(isWebSocketEnvelope({ ...valid, payload: { ...valid.payload, services: [{ ...valid.payload.services[0], watts: '100' }] } }), false);
