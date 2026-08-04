from datetime import date

from pydantic import BaseModel, Field


class CatalogExerciseOut(BaseModel):
    id: int
    category: str
    name: str
    description: str | None = None
    video_url: str | None = None
    sort_order: int = 0
    is_active: bool = True
    completed: bool = False
    selected: bool = False

    model_config = {"from_attributes": True}


class DaySectionOut(BaseModel):
    key: str
    title: str
    kind: str  # fixed | variants | bonus | muscle | checklist | extra
    required: bool = True
    section_completed: bool = False
    badge: str | None = None
    choice_made: bool | None = None
    can_add: bool = False
    options: list[CatalogExerciseOut] = Field(default_factory=list)
    exercises: list[CatalogExerciseOut] = Field(default_factory=list)
    muscle_group: str | None = None
    muscle_label: str | None = None


class ExtraIn(BaseModel):
    kind: str  # posture | glutes


class DayPlanOut(BaseModel):
    plan_date: date
    title: str = "План на день"
    sections: list[DaySectionOut]
    extras: list[DaySectionOut] = Field(default_factory=list)
    base_completed: int
    base_total: int
    base_done: bool
    bonus_completed: int
    bonus_total: int
    muscle_completed: int
    muscle_total: int


class ToggleProgressIn(BaseModel):
    completed: bool
    block: str = "base"  # base | bonus | muscle
    catalog_exercise_id: int | None = None
    section: str | None = None  # slot1 | slot2 | slot3 | posture_base | neck
    plan_date: date | None = None


class CompleteBaseIn(BaseModel):
    plan_date: date | None = None


class ChooseIn(BaseModel):
    slot: str  # slot3 | neck
    catalog_exercise_id: int


class CatalogAddIn(BaseModel):
    category: str
    name: str
    description: str | None = None
    video_url: str | None = None
    sort_order: int = 0


class CatalogUpdateIn(BaseModel):
    category: str | None = None
    name: str | None = None
    description: str | None = None
    video_url: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: int
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    is_admin: bool = False

    model_config = {"from_attributes": True}


class DaySummary(BaseModel):
    plan_date: date
    title: str
    completed_count: int
    total_count: int
    done: bool


class ActivityLogOut(BaseModel):
    id: int
    log_date: date
    kind: str
    kind_label: str
    comment: str

    model_config = {"from_attributes": True}


class SuccessDayOut(BaseModel):
    date: date
    base_done: bool
    bonus_count: int
    exercise_count: int = 0
    log_kinds: list[str] = Field(default_factory=list)


class MonthSuccessOut(BaseModel):
    year: int
    month: int
    label: str
    days_in_month: int
    base_closed_days: int
    bonus_total: int
    days: list[SuccessDayOut] = Field(default_factory=list)
    logs: list[ActivityLogOut] = Field(default_factory=list)


class ActivityLogIn(BaseModel):
    log_date: date
    kind: str = "note"  # strength | face | note
    comment: str = ""


class DaySuccessOut(BaseModel):
    date: date
    base_done: bool
    base_completed: int
    base_total: int
    base_exercises: list[CatalogExerciseOut] = Field(default_factory=list)
    bonus_exercises: list[CatalogExerciseOut] = Field(default_factory=list)
    logs: list[ActivityLogOut] = Field(default_factory=list)
    activity_kinds: list[dict[str, str]] = Field(default_factory=list)
