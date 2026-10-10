const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string' && value.length > 0;
const integer = value => Number.isSafeInteger(value) && value >= 0;
const timestamp = value => typeof value === 'string' &&
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));

export function isWebSocketEnvelope(value) {
  if (!object(value) || value.type !== 'snapshot' || !timestamp(value.sent_at)) return false;
  const payload = value.payload;
  const identity = payload?.contract?.identity;
  const identityStrings = ['site_id', 'run_id', 'config_hash', 'catalog_version', 'policy_version', 'model_version', 'observation_time'];
  const validService = item => object(item) && text(item.id) && text(item.name) &&
    ['T1', 'T2', 'T3'].includes(item.tier) && text(item.feeder) && integer(item.watts) &&
    typeof item.requested === 'boolean' && typeof item.modeled_served === 'boolean';
  return object(payload) && object(identity) && identityStrings.every(key => text(identity[key])) &&
    timestamp(identity.observation_time) && integer(identity.server_epoch) &&
    integer(identity.state_revision) && integer(payload.control_revision) && integer(payload.published_revision) &&
    timestamp(payload.generated_at) &&
    Array.isArray(payload.services) && payload.services.every(validService) && object(payload.source) &&
    integer(payload.source.capacity_w);
}
