from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sqlite_add_missing_columns)

    async with SessionLocal() as session:
        n = await services.seed_catalog_if_empty(session)
        if n:
            import logging

            logging.getLogger(__name__).info("Seeded %s catalog exercises", n)
