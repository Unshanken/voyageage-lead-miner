from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from leadminer.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


settings = get_settings()
engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_database() -> None:
    from leadminer.models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_sqlite_phase2_migration()


def _apply_sqlite_phase2_migration() -> None:
    """Apply additive Phase 2 columns to Phase 1 local SQLite databases.

    Shared/PostgreSQL deployments should use a normal migration tool before they are introduced.
    """
    if engine.dialect.name != "sqlite" or not inspect(engine).has_table("companies"):
        return
    existing = {column["name"] for column in inspect(engine).get_columns("companies")}
    additions = {
        "crawl_duration_ms": "INTEGER",
        "ai_native_candidate": "BOOLEAN NOT NULL DEFAULT 0",
        "providers_detected": "JSON NOT NULL DEFAULT '[]'",
        "has_ai_docs": "BOOLEAN NOT NULL DEFAULT 0",
        "has_model_selector_signal": "BOOLEAN NOT NULL DEFAULT 0",
        "has_ai_pricing_signal": "BOOLEAN NOT NULL DEFAULT 0",
        "has_ai_jobs_signal": "BOOLEAN NOT NULL DEFAULT 0",
        "llm_integration_signal": "BOOLEAN NOT NULL DEFAULT 0",
        "ai_signal_count": "INTEGER NOT NULL DEFAULT 0",
        "strong_ai_signal_count": "INTEGER NOT NULL DEFAULT 0",
        "weak_ai_signal_count": "INTEGER NOT NULL DEFAULT 0",
        "crawl_summary": "JSON NOT NULL DEFAULT '{}'",
    }
    with engine.begin() as connection:
        for column, definition in additions.items():
            if column not in existing:
                connection.execute(text(f"ALTER TABLE companies ADD COLUMN {column} {definition}"))
        connection.execute(
            text("UPDATE companies SET crawl_status = 'PENDING' WHERE crawl_status = 'pending'")
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_companies_crawl_status ON companies (crawl_status)")
        )


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
