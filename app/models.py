from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Catalog categories
CAT_SLOT1 = "slot1"
CAT_SLOT2 = "slot2"
CAT_SLOT3 = "slot3"
CAT_POSTURE = "posture"
CAT_NECK = "neck"
CAT_MUSCLE_GLUTES = "muscle_glutes_legs"
CAT_MUSCLE_ARMS = "muscle_arms"
CAT_MUSCLE_CORE = "muscle_core_back"

MUSCLE_GROUPS = (CAT_MUSCLE_GLUTES, CAT_MUSCLE_ARMS, CAT_MUSCLE_CORE)

MUSCLE_LABELS = {
    CAT_MUSCLE_GLUTES: "Попа / ноги",
    CAT_MUSCLE_ARMS: "Руки",
    CAT_MUSCLE_CORE: "Кор / спина",
}

CATEGORY_LABELS = {
    CAT_SLOT1: "1. Носочки/рамка",
    CAT_SLOT2: "2. Апоневроз",
    CAT_SLOT3: "Декольте",
    CAT_POSTURE: "Осанка",
    CAT_NECK: "Шея",
    **MUSCLE_LABELS,
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    day_plans: Mapped[list["UserDayPlan"]] = relationship(back_populates="user")
    completions: Mapped[list["UserCompletion"]] = relationship(back_populates="user")
    activity_logs: Mapped[list["ActivityLog"]] = relationship(back_populates="user")


class CatalogExercise(Base):
    """Shared library of exercises by category."""

    __tablename__ = "catalog_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserDayPlan(Base):
    """Frozen personal day: posture picks, muscle group, user choices."""

    __tablename__ = "user_day_plans"
    __table_args__ = (UniqueConstraint("user_id", "plan_date", name="uq_user_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_date: Mapped[date] = mapped_column(Date, index=True)

    # comma-separated catalog ids, e.g. "12,15,18"
    posture_base_ids: Mapped[str] = mapped_column(String(255), default="")
    posture_bonus_ids: Mapped[str] = mapped_column(String(255), default="")
    neck_exercise_ids: Mapped[str] = mapped_column(String(255), default="")
    muscle_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    muscle_exercise_ids: Mapped[str] = mapped_column(String(255), default="")
    glute_bonus_ids: Mapped[str] = mapped_column(String(255), default="")

    slot3_choice_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    neck_choice_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # One checkbox per block (variants below are links only)
    slot3_done: Mapped[bool] = mapped_column(Boolean, default=False)
    posture_base_done: Mapped[bool] = mapped_column(Boolean, default=False)
    neck_done: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="day_plans")


class UserCompletion(Base):
    __tablename__ = "user_completions"
    __table_args__ = (
        UniqueConstraint("user_id", "catalog_exercise_id", "plan_date", "block", name="uq_completion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    catalog_exercise_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_exercises.id", ondelete="CASCADE"), index=True
    )
    plan_date: Mapped[date] = mapped_column(Date, index=True)
    block: Mapped[str] = mapped_column(String(32))  # base | bonus | muscle
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="completions")


ACTIVITY_KINDS = {
    "strength": "Силовая",
    "face": "Фейсфитнес",
    "note": "Заметка",
}


class ActivityLog(Base):
    """Free-form diary: strength / face fitness / note with comment."""

    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    log_date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(32), default="note")
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="activity_logs")
