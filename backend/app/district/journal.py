"""District audit journal on the existing SQLite history store.

Each accepted action commits one record holding the complete resulting modeled state, so a
restart restores the last committed revision and never a partial one. Playback only reads.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.storage.history import HistoryRecord

SITE = "gnitc-demo"
KIND = "district_action"


class DistrictJournal:
    def __init__(self, store):
        self.store = store

    def commit(self, run_id, record_id, revision, payload):
        return self.store.append(SITE, run_id, KIND, record_id, datetime.now(timezone.utc).isoformat(), revision, payload)

    def latest(self):
        with Session(self.store.engine) as session:
            row = session.exec(select(HistoryRecord).where(HistoryRecord.site_id == SITE, HistoryRecord.kind == KIND)
                               .order_by(HistoryRecord.seq.desc()).limit(1)).first()
        return None if row is None else {"run_id": row.run_id, "revision": row.revision, "record_id": row.record_id,
                                         "payload": json.loads(row.payload_json)}

    def page(self, run_id, after=0, limit=200):
        return self.store.page(SITE, run_id, after=after, limit=limit, kind=KIND)

    def runs(self):
        return self.store.runs(SITE)
