from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base


def _ensure_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite"):
        return
    path = url.split("///", maxsplit=1)[-1]
    if path and path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
_ensure_sqlite_dir(settings.database_url)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def migrate_db() -> None:
    inspector = inspect(engine)
    if "sources" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("sources")}
    statements: list[str] = []
    if "source_kind" not in columns:
        statements.append("ALTER TABLE sources ADD COLUMN source_kind VARCHAR(16) DEFAULT 'public'")
    if "invite_hash" not in columns:
        statements.append("ALTER TABLE sources ADD COLUMN invite_hash VARCHAR(128)")
    if "invite_link" not in columns:
        statements.append("ALTER TABLE sources ADD COLUMN invite_link VARCHAR(512)")
    if "telegram_peer_id" not in columns:
        statements.append("ALTER TABLE sources ADD COLUMN telegram_peer_id VARCHAR(64)")
    if "telegram_access_hash" not in columns:
        statements.append("ALTER TABLE sources ADD COLUMN telegram_access_hash VARCHAR(64)")
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(text("UPDATE sources SET source_kind = 'public' WHERE source_kind IS NULL"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_db()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
