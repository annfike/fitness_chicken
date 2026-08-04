from collections.abc import AsyncGenerator
from pathlib import Path
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def resolve_sqlite_file(database_url: str | None = None) -> Path | None:
    """Return filesystem path for sqlite URL, if applicable."""
    url = (database_url or get_settings().database_url).strip()
    if "sqlite" not in url or ":///" not in url:
        return None
    raw = url.split(":///", 1)[1]
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


def _sqlite_add_missing_columns(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if "user_day_plans" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("user_day_plans")}
    for name, ddl in (
        ("slot3_done", "ALTER TABLE user_day_plans ADD COLUMN slot3_done BOOLEAN DEFAULT 0"),
        ("posture_base_done", "ALTER TABLE user_day_plans ADD COLUMN posture_base_done BOOLEAN DEFAULT 0"),
        ("neck_done", "ALTER TABLE user_day_plans ADD COLUMN neck_done BOOLEAN DEFAULT 0"),
        ("neck_exercise_ids", "ALTER TABLE user_day_plans ADD COLUMN neck_exercise_ids VARCHAR(255) DEFAULT ''"),
        ("glute_bonus_ids", "ALTER TABLE user_day_plans ADD COLUMN glute_bonus_ids VARCHAR(255) DEFAULT ''"),
    ):
        if name not in cols:
            sync_conn.execute(text(ddl))


async def init_db() -> None:
    from app import models  # noqa: F401
    from app import services

    db_path = resolve_sqlite_file()
    if db_path is not None:
        logger.info(
            "SQLite file: %s (exists=%s, size=%s, cwd=%s)",
            db_path,
            db_path.exists(),
            db_path.stat().st_size if db_path.exists() else 0,
            Path.cwd(),
        )
    else:
        logger.info("DATABASE_URL=%s", get_settings().database_url)

    async with engine.begin() as conn:
        # create_all only adds missing tables — it does NOT drop or wipe data
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sqlite_add_missing_columns)

    async with SessionLocal() as session:
        n = await services.seed_catalog_if_empty(session)
        if n:
            logger.warning(
                "Catalog was empty — seeded %s exercises from catalog_seed.json "
                "(this usually means a NEW empty database file after deploy)",
                n,
            )
        else:
            logger.info("Catalog already has data — seed skipped")
