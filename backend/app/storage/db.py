"""One database lifecycle and serialized writer per application instance."""
import logging
import os
import sqlite3
import tempfile
import threading
from pathlib import Path
from sqlalchemy import event
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

log = logging.getLogger(__name__)

class Storage:
    def __init__(self, url=None):
        url = url or os.environ.get('DATABASE_URL', 'sqlite:///prioritygrid.db')
        options = {'poolclass': StaticPool} if url == 'sqlite://' else {}
        self.engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 15}, **options)
        if url.startswith('sqlite:'):
            event.listen(self.engine, 'connect', lambda dbapi, _: dbapi.execute('PRAGMA foreign_keys=ON'))
        self.lock = threading.Lock()
        self.degraded = False
        self.degraded_reason = None

    def init(self):
        try:
            with self.engine.begin() as connection:
                connection.execute(text('PRAGMA journal_mode=WAL'))
            SQLModel.metadata.create_all(self.engine)
            with self.engine.begin() as connection:
                connection.exec_driver_sql('CREATE TABLE IF NOT EXISTS schema_migration (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
                current = connection.exec_driver_sql('SELECT MAX(version) FROM schema_migration').scalar() or 0
                if current < 1:
                    connection.exec_driver_sql('CREATE UNIQUE INDEX IF NOT EXISTS uq_ack_identity ON acknowledgment (run_id, device_boot, sequence, session)')
                    for table in ('observation', 'command', 'decision', 'transition', 'incident', 'acknowledgment'):
                        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS {table}_run_insert BEFORE INSERT ON {table} WHEN NOT EXISTS (SELECT 1 FROM run WHERE run_id=NEW.run_id) BEGIN SELECT RAISE(ABORT, 'unknown run_id'); END")
                        connection.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS {table}_run_update BEFORE UPDATE OF run_id ON {table} WHEN NOT EXISTS (SELECT 1 FROM run WHERE run_id=NEW.run_id) BEGIN SELECT RAISE(ABORT, 'unknown run_id'); END")
                    connection.exec_driver_sql("INSERT INTO schema_migration(version, applied_at) VALUES (1, datetime('now'))")
        except Exception:
            self.degraded = True
            self.degraded_reason = 'Database initialization or migration failed'
            log.exception('Database initialization failed')

    def commit(self, session):
        if self.degraded:
            return False
        with self.lock:
            try:
                session.commit()
                return True
            except Exception:
                session.rollback()
                self.degraded = True
                self.degraded_reason = 'Database write failed'
                log.exception('Database write failed')
                return False

    def backup(self, path):
        return backup_sqlite(self.engine, path, self.lock)


def backup_sqlite(engine, path, lock):
    """Create a consistent SQLite backup and replace the target only after integrity checks."""
    target = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=target.parent)
    os.close(fd)
    source = engine.raw_connection()
    destination = None
    try:
        with lock:
            destination = sqlite3.connect(temporary)
            source.driver_connection.backup(destination)
            if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise sqlite3.DatabaseError('backup integrity_check failed')
            if destination.execute('PRAGMA foreign_key_check').fetchall():
                raise sqlite3.DatabaseError('backup foreign_key_check failed')
            tables = {row[0] for row in destination.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'run' in tables:
                for table in ('observation', 'command', 'decision', 'transition', 'incident', 'acknowledgment'):
                    if table in tables and destination.execute(
                        f'SELECT 1 FROM {table} child LEFT JOIN run parent ON parent.run_id=child.run_id WHERE parent.run_id IS NULL LIMIT 1'
                    ).fetchone():
                        raise sqlite3.DatabaseError(f'backup contains an orphaned {table} row')
            if {'historyrecord', 'historyrun'} <= tables and destination.execute(
                'SELECT 1 FROM historyrecord child LEFT JOIN historyrun parent '
                'ON parent.site_id=child.site_id AND parent.run_id=child.run_id WHERE parent.run_id IS NULL LIMIT 1'
            ).fetchone():
                raise sqlite3.DatabaseError('backup contains a history record without its run')
            destination.close()
            destination = None
            os.replace(temporary, target)
        return target
    finally:
        if destination is not None:
            destination.close()
        source.close()
        if os.path.exists(temporary):
            os.unlink(temporary)
