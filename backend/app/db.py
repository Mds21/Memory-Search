from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

_s = get_settings()
_is_sqlite = _s.database_url.startswith("sqlite")
if _is_sqlite:
    _s.data_path  # ensure folder exists
engine = create_engine(
    _s.database_url,
    connect_args={"check_same_thread": False, "timeout": 30} if _is_sqlite else {},
    pool_pre_ping=True,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401
    Base.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns():
    """create_all() never alters existing tables, so columns added later are added here (nullable, no data change)."""
    from sqlalchemy import inspect, text
    have = {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.begin() as conn:
        if "google_sub" not in have:
            conn.execute(text("ALTER TABLE users ADD COLUMN google_sub VARCHAR(64)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)"))
