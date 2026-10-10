import uuid
import time
from datetime import datetime, timezone

RUN_ID = str(uuid.uuid4())
SERVER_EPOCH = int(time.time())

def get_run_identity(site_id: str, config_hash: str, catalog_version: str, revision: int) -> dict:
    return {
        "site_id": site_id,
        "run_id": RUN_ID,
        "server_epoch": SERVER_EPOCH,
        "config_hash": config_hash,
        "catalog_version": catalog_version,
        "policy_version": "1.0",
        "model_version": "1.0", # AI/ML model version
        "state_revision": revision,
        "observation_time": datetime.now(timezone.utc).isoformat()
    }
