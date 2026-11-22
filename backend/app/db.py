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
    from sqlalchemy import text
    with engine.begin() as conn:  # one account per phone number / username (NULLs allowed)
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_phone ON users (phone)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username ON users (username)"))


def _add_missing_columns():
    """Tiny forward-only migration: add columns introduced after a database was created (create_all never alters tables)."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl = col.type.compile(dialect=engine.dialect)
                default = ""
                if col.default is not None and getattr(col.default, "is_scalar", False):
                    v = col.default.arg
                    default = f" DEFAULT {int(v) if isinstance(v, bool) else repr(v)}"
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl}{default}'))
