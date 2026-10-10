"""One database lifecycle and serialized writer per application instance."""
import logging
import os
import threading
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

log = logging.getLogger(__name__)

class Storage:
    def __init__(self, url=None):
        url = url or os.environ.get('DATABASE_URL', 'sqlite:///prioritygrid.db')
        options = {'poolclass': StaticPool} if url == 'sqlite://' else {}
        self.engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 15}, **options)
        self.lock = threading.Lock()
        self.degraded = False

    def init(self):
        try:
            with self.engine.begin() as connection:
                connection.execute(text('PRAGMA journal_mode=WAL'))
            SQLModel.metadata.create_all(self.engine)
        except Exception:
            self.degraded = True
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
                log.exception('Database write failed')
                return False
