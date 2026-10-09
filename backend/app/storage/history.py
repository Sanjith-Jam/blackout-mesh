"""Durable ordered history. Playback reads these records; it never runs control."""
import json
import threading
from sqlalchemy import Index, UniqueConstraint, delete
from sqlmodel import SQLModel, Field, Session, create_engine, select


class HistoryRecord(SQLModel, table=True):
    __table_args__ = (
        Index("history_scope_cursor", "site_id", "run_id", "seq"),
        Index("history_scope_time", "site_id", "run_id", "timestamp"),
        UniqueConstraint("site_id", "run_id", "record_id"),
        {"sqlite_autoincrement": True},
    )
    seq: int | None = Field(default=None, primary_key=True)
    site_id: str
    run_id: str
    kind: str
    record_id: str
    timestamp: str
    revision: int
    provenance: str = "SIMULATED"
    payload_json: str


class HistoryRun(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("site_id", "run_id"),)
    id: int | None = Field(default=None, primary_key=True)
    site_id: str = Field(index=True)
    run_id: str
    started_at: str
    pruned_through: int = 0


class HistoryStore:
    def __init__(self, path):
        self.engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
        self.lock = threading.RLock()
        SQLModel.metadata.create_all(self.engine)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            connection.exec_driver_sql("PRAGMA busy_timeout=5000")

    def append(self, site, run, kind, record_id, timestamp, revision, payload):
        with self.lock, Session(self.engine) as session:
            duplicate = session.exec(select(HistoryRecord).where(
                HistoryRecord.site_id == site, HistoryRecord.run_id == run,
                HistoryRecord.record_id == record_id)).first()
            if duplicate:
                return duplicate.seq
            known_run = session.exec(select(HistoryRun).where(
                HistoryRun.site_id == site, HistoryRun.run_id == run)).first()
            if not known_run:
                session.add(HistoryRun(site_id=site, run_id=run, started_at=timestamp))
            record = HistoryRecord(site_id=site, run_id=run, kind=kind, record_id=record_id,
                                   timestamp=timestamp, revision=revision,
                                   payload_json=json.dumps(payload, allow_nan=False))
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.seq

    def page(self, site, run, *, after=0, limit=200, kind=None, start=None, end=None):
        with Session(self.engine) as session:
            query = select(HistoryRecord).where(
                HistoryRecord.site_id == site, HistoryRecord.run_id == run,
                HistoryRecord.seq > after)
            if kind:
                query = query.where(HistoryRecord.kind == kind)
            if start:
                query = query.where(HistoryRecord.timestamp >= start)
            if end:
                query = query.where(HistoryRecord.timestamp <= end)
            rows = session.exec(query.order_by(HistoryRecord.seq).limit(limit + 1)).all()
            known_run = session.exec(select(HistoryRun).where(
                HistoryRun.site_id == site, HistoryRun.run_id == run)).first()
            items = [dict(seq=row.seq, record_id=row.record_id, site_id=row.site_id,
                          run_id=row.run_id, kind=row.kind, timestamp=row.timestamp,
                          revision=row.revision, provenance=row.provenance,
                          payload=json.loads(row.payload_json)) for row in rows[:limit]]
            return {"items": items, "next_cursor": items[-1]["seq"] if len(rows) > limit else None,
                    "retention_gap": bool(known_run and after and after <= known_run.pruned_through),
                    "pruned_through": known_run.pruned_through if known_run else 0}

    def runs(self, site):
        with Session(self.engine) as session:
            return [row.model_dump(exclude={"id"}) for row in session.exec(
                select(HistoryRun).where(HistoryRun.site_id == site)
                .order_by(HistoryRun.id.desc())).all()]

    def prune(self, before):
        # Explicit 30-day raw retention, no irreversible output-only aggregation.
        with self.lock, Session(self.engine) as session:
            old = session.exec(select(HistoryRecord).where(HistoryRecord.timestamp < before)).all()
            for row in old:
                run = session.exec(select(HistoryRun).where(
                    HistoryRun.site_id == row.site_id, HistoryRun.run_id == row.run_id)).one()
                run.pruned_through = max(run.pruned_through, row.seq)
                session.add(run)
            session.exec(delete(HistoryRecord).where(HistoryRecord.timestamp < before))
            session.commit()
            return len(old)

