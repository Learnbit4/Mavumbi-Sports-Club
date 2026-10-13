from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .config import get_settings

_engine = None
_Session = None


def configure(url: str | None = None):
    """(Re)configure the global engine. Tests pass sqlite://; production uses MySQL."""
    global _engine, _Session
    url = url or get_settings().db_url
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool
        kw = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    else:
        kw = {"pool_pre_ping": True, "pool_recycle": 1800}
    _engine = create_engine(url, **kw)
    if url.startswith("sqlite"):
        event.listen(_engine, "connect", lambda c, _r: c.execute("PRAGMA foreign_keys=ON"))
    _Session = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine():
    return _engine or configure()


def new_session():
    get_engine()
    return _Session()


@contextmanager
def session_scope():
    """One unit of work = one transaction. Commits on success, rolls back on any error."""
    s = new_session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db():
    from .models import Base
    Base.metadata.create_all(get_engine())
