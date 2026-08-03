from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    ACTIVITY_KINDS,
    CAT_MUSCLE_GLUTES,
    CAT_NECK,
    CAT_POSTURE,
    CAT_SLOT1,
    CAT_SLOT2,
    CAT_SLOT3,
    CATEGORY_LABELS,
    MUSCLE_GROUPS,
    MUSCLE_LABELS,
    ActivityLog,
    CatalogExercise,
    User,
    UserCompletion,
    UserDayPlan,
)
from app.schemas import (
    ActivityLogOut,
    CatalogExerciseOut,
    DayPlanOut,
    DaySectionOut,
    DaySuccessOut,
    DaySummary,
    MonthSuccessOut,
    SuccessDayOut,
)

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog_seed.json"


def _parse_ids(raw: str | None) -> list[int]:
    if not raw or not raw.strip():
        return []
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


def _ids_to_str(ids: list[int]) -> str:
    return ",".join(str(i) for i in ids)


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday


def today_in_tz() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


async def upsert_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        session.add(user)
    else:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
    await session.commit()
    await session.refresh(user)
    return user


async def list_catalog(
    session: AsyncSession, category: str | None = None, active_only: bool = True
) -> list[CatalogExercise]:
    q = select(CatalogExercise).order_by(CatalogExercise.sort_order, CatalogExercise.id)
    if category:
        q = q.where(CatalogExercise.category == category)
    if active_only:
        q = q.where(CatalogExercise.is_active.is_(True))
    result = await session.execute(q)
    return list(result.scalars().all())


async def add_catalog_exercise(
    session: AsyncSession,
    *,
    category: str,
    name: str,
    description: str | None = None,
    video_url: str | None = None,
    sort_order: int = 0,
) -> CatalogExercise:
    row = CatalogExercise(
        category=category,
        name=name,
        description=description,
        video_url=video_url,
        sort_order=sort_order,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_catalog_exercise(
    session: AsyncSession,
    exercise_id: int,
    *,
    category: str | None = None,
    name: str | None = None,
    description: str | None = None,
    video_url: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> CatalogExercise:
    result = await session.execute(select(CatalogExercise).where(CatalogExercise.id == exercise_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError("Exercise not found")
    if category is not None:
        row.category = category
    if name is not None:
        row.name = name
    if description is not None:
        row.description = description
    if video_url is not None:
        row.video_url = video_url or None
    if sort_order is not None:
        row.sort_order = sort_order
    if is_active is not None:
        row.is_active = is_active
    await session.commit()
    await session.refresh(row)
    return row


async def delete_catalog_exercise(session: AsyncSession, exercise_id: int) -> None:
    result = await session.execute(select(CatalogExercise).where(CatalogExercise.id == exercise_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError("Exercise not found")
    await session.delete(row)
    await session.commit()


async def seed_catalog_if_empty(session: AsyncSession) -> int:
    result = await session.execute(select(CatalogExercise.id).limit(1))
    if result.scalar_one_or_none() is not None:
        return 0
    return await _load_seed(session)


async def reload_catalog_from_seed(session: AsyncSession) -> int:
    """Wipe catalog and reload from catalog_seed.json (admin)."""
    rows = await list_catalog(session, active_only=False)
    for row in rows:
        await session.delete(row)
    await session.flush()
    # also clear day plans so stale ids don't confuse
    result = await session.execute(select(UserDayPlan))
    for plan in result.scalars().all():
        await session.delete(plan)
    await session.flush()
    return await _load_seed(session)


async def _load_seed(session: AsyncSession) -> int:
    if not SEED_PATH.exists():
        return 0
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    count = 0
    for i, item in enumerate(data):
        session.add(
            CatalogExercise(
                category=item["category"],
                name=item.get("name") or (item.get("description") or "Без названия")[:80],
                description=item.get("description"),
                video_url=item.get("video_url"),
                sort_order=item.get("sort_order", i),
            )
        )
        count += 1
    await session.commit()
    return count


def is_admin_user(user: User) -> bool:
    admins = get_settings().admin_id_set
    return bool(admins) and user.telegram_id in admins


async def _fixed_slot(session: AsyncSession, category: str) -> CatalogExercise | None:
    items = await list_catalog(session, category)
    return items[0] if items else None


async def _category_done_this_week(
    session: AsyncSession, user_id: int, plan_date: date, category: str
) -> set[int]:
    start = week_start(plan_date)
    result = await session.execute(
        select(UserCompletion.catalog_exercise_id).where(
            UserCompletion.user_id == user_id,
            UserCompletion.completed.is_(True),
            UserCompletion.plan_date >= start,
            UserCompletion.plan_date <= plan_date,
            UserCompletion.block.in_(("base", "bonus")),
        )
    )
    ids = set(result.scalars().all())
    if not ids:
        return set()
    result = await session.execute(
        select(CatalogExercise.id).where(
            CatalogExercise.id.in_(ids),
            CatalogExercise.category == category,
        )
    )
    return set(result.scalars().all())


def _pick_n(pool: list[CatalogExercise], n: int, rng: random.Random) -> list[CatalogExercise]:
    if not pool:
        return []
    if len(pool) <= n:
        shuffled = pool[:]
        rng.shuffle(shuffled)
        return shuffled
    return rng.sample(pool, n)


async def _pick_category(
    session: AsyncSession,
    user_id: int,
    plan_date: date,
    category: str,
    n: int,
    exclude: set[int],
    rng: random.Random,
) -> list[CatalogExercise]:
    all_items = await list_catalog(session, category)
    if not all_items:
        return []
    done = await _category_done_this_week(session, user_id, plan_date, category)
    remaining = [e for e in all_items if e.id not in done and e.id not in exclude]
    if len(remaining) < n:
        remaining = [e for e in all_items if e.id not in exclude] or all_items
    return _pick_n(remaining, n, rng)


async def _pick_posture(
    session: AsyncSession,
    user_id: int,
    plan_date: date,
    n: int,
    exclude: set[int],
    rng: random.Random,
) -> list[CatalogExercise]:
    return await _pick_category(session, user_id, plan_date, CAT_POSTURE, n, exclude, rng)


async def _muscle_group_counts_this_week(
    session: AsyncSession, user_id: int, plan_date: date
) -> dict[str, int]:
    start = week_start(plan_date)
    result = await session.execute(
        select(UserDayPlan).where(
            UserDayPlan.user_id == user_id,
            UserDayPlan.plan_date >= start,
            UserDayPlan.plan_date < plan_date,
        )
    )
    plans = result.scalars().all()
    counts = {g: 0 for g in MUSCLE_GROUPS}
    for p in plans:
        if not p.muscle_group:
            continue
        # count if any muscle completion that day
        mids = _parse_ids(p.muscle_exercise_ids)
        if not mids:
            continue
        result = await session.execute(
            select(UserCompletion.id).where(
                UserCompletion.user_id == user_id,
                UserCompletion.plan_date == p.plan_date,
                UserCompletion.block == "muscle",
                UserCompletion.completed.is_(True),
                UserCompletion.catalog_exercise_id.in_(mids),
            ).limit(1)
        )
        if result.scalar_one_or_none() is not None:
            counts[p.muscle_group] = counts.get(p.muscle_group, 0) + 1
    return counts


def _choose_muscle_group(counts: dict[str, int]) -> str:
    # lowest count, stable order among ties
    return min(MUSCLE_GROUPS, key=lambda g: (counts.get(g, 0), MUSCLE_GROUPS.index(g)))


async def get_or_create_day_plan(
    session: AsyncSession, user: User, plan_date: date | None = None
) -> UserDayPlan:
    plan_date = plan_date or today_in_tz()
    result = await session.execute(
        select(UserDayPlan).where(UserDayPlan.user_id == user.id, UserDayPlan.plan_date == plan_date)
    )
    existing = result.scalar_one_or_none()
    if existing:
        changed = False
        # Шея как осанка: 3 упражнения; добираем, если в плане меньше, чем есть в каталоге
        neck_ids = list(dict.fromkeys(_parse_ids(existing.neck_exercise_ids)))
        neck_catalog = await list_catalog(session, CAT_NECK)
        target = min(3, len(neck_catalog))
        if len(neck_ids) < target:
            rng = random.Random(f"{user.id}:{plan_date.isoformat()}:neck")
            neck = await _pick_category(session, user.id, plan_date, CAT_NECK, 3, set(), rng)
            existing.neck_exercise_ids = _ids_to_str([e.id for e in neck])
            changed = True
        # Силовая в базе: одно упражнение на попу
        muscle_ids = _parse_ids(existing.muscle_exercise_ids)
        if existing.muscle_group != CAT_MUSCLE_GLUTES or len(muscle_ids) != 1:
            rng = random.Random(f"{user.id}:{plan_date.isoformat()}:muscle")
            glute = await _pick_category(
                session, user.id, plan_date, CAT_MUSCLE_GLUTES, 1, set(), rng
            )
            existing.muscle_group = CAT_MUSCLE_GLUTES
            existing.muscle_exercise_ids = _ids_to_str([e.id for e in glute])
            muscle_ids = [e.id for e in glute]
            changed = True
        # Доп. блоки стартуют пустыми — упражнения добавляются кнопками «Еще…»
        if changed:
            await session.commit()
            await session.refresh(existing)
        return existing

    rng = random.Random(f"{user.id}:{plan_date.isoformat()}")
    base = await _pick_posture(session, user.id, plan_date, 3, set(), rng)
    neck = await _pick_category(session, user.id, plan_date, CAT_NECK, 3, set(), rng)
    glute = await _pick_category(session, user.id, plan_date, CAT_MUSCLE_GLUTES, 1, set(), rng)

    day = UserDayPlan(
        user_id=user.id,
        plan_date=plan_date,
        posture_base_ids=_ids_to_str([e.id for e in base]),
        posture_bonus_ids="",
        neck_exercise_ids=_ids_to_str([e.id for e in neck]),
        muscle_group=CAT_MUSCLE_GLUTES,
        muscle_exercise_ids=_ids_to_str([e.id for e in glute]),
        glute_bonus_ids="",
    )
    session.add(day)
    await session.commit()
    await session.refresh(day)
    return day


async def _completions_map(
    session: AsyncSession, user_id: int, plan_date: date
) -> dict[tuple[int, str], bool]:
    result = await session.execute(
        select(UserCompletion).where(
            UserCompletion.user_id == user_id,
            UserCompletion.plan_date == plan_date,
        )
    )
    return {(r.catalog_exercise_id, r.block): r.completed for r in result.scalars().all()}


async def _by_ids(session: AsyncSession, ids: list[int]) -> list[CatalogExercise]:
    if not ids:
        return []
    result = await session.execute(select(CatalogExercise).where(CatalogExercise.id.in_(ids)))
    by_id = {e.id: e for e in result.scalars().all()}
    return [by_id[i] for i in ids if i in by_id]


def _to_out(
    ex: CatalogExercise,
    *,
    completed: bool = False,
    selected: bool = False,
) -> CatalogExerciseOut:
    return CatalogExerciseOut(
        id=ex.id,
        category=ex.category,
        name=ex.name,
        description=ex.description,
        video_url=ex.video_url,
        sort_order=ex.sort_order,
        completed=completed,
        selected=selected,
    )


async def build_day_plan(session: AsyncSession, user: User, plan_date: date | None = None) -> DayPlanOut:
    plan_date = plan_date or today_in_tz()
    day = await get_or_create_day_plan(session, user, plan_date)
    done = await _completions_map(session, user.id, plan_date)

    sections: list[DaySectionOut] = []
    base_items: list[tuple[CatalogExercise, str]] = []  # ex, for counting fixed ones

    # Slot 1, 2, 3 — по одному фиксированному упражнению
    for cat, key, title in (
        (CAT_SLOT1, "slot1", CATEGORY_LABELS[CAT_SLOT1]),
        (CAT_SLOT2, "slot2", CATEGORY_LABELS[CAT_SLOT2]),
        (CAT_SLOT3, "slot3", CATEGORY_LABELS[CAT_SLOT3]),
    ):
        ex = await _fixed_slot(session, cat)
        exercises = []
        if ex:
            exercises = [_to_out(ex, completed=done.get((ex.id, "base"), False))]
            base_items.append((ex, "fixed"))
        sections.append(
            DaySectionOut(
                key=key,
                title=title,
                kind="fixed",
                required=True,
                exercises=exercises,
            )
        )

    # Posture — one field, checkbox per exercise
    posture_base = await _by_ids(session, _parse_ids(day.posture_base_ids))
    posture_outs = [_to_out(e, completed=done.get((e.id, "base"), False)) for e in posture_base]
    sections.append(
        DaySectionOut(
            key="posture_base",
            title=CATEGORY_LABELS[CAT_POSTURE],
            kind="checklist",
            required=True,
            section_completed=bool(posture_outs) and all(e.completed for e in posture_outs),
            options=posture_outs,
        )
    )

    # Neck — same as posture: one field, checkbox per exercise
    neck_items = await _by_ids(session, _parse_ids(day.neck_exercise_ids))
    neck_outs = [_to_out(e, completed=done.get((e.id, "base"), False)) for e in neck_items]
    sections.append(
        DaySectionOut(
            key="neck",
            title=CATEGORY_LABELS[CAT_NECK],
            kind="checklist",
            required=True,
            section_completed=bool(neck_outs) and all(e.completed for e in neck_outs),
            options=neck_outs,
        )
    )

    # Попа — в базе, одно упражнение
    muscle_ex = await _by_ids(session, _parse_ids(day.muscle_exercise_ids))
    muscle_outs = [
        _to_out(
            e,
            completed=done.get((e.id, "base"), False) or done.get((e.id, "muscle"), False),
        )
        for e in muscle_ex
    ]
    sections.append(
        DaySectionOut(
            key="muscle",
            title="Попа",
            kind="checklist",
            required=True,
            section_completed=bool(muscle_outs) and all(e.completed for e in muscle_outs),
            muscle_group=day.muscle_group,
            muscle_label=MUSCLE_LABELS.get(day.muscle_group or ""),
            options=muscle_outs,
        )
    )

    # Extra packs — пустые на старте, наполняются кнопками «Еще…»
    posture_bonus = await _by_ids(session, _parse_ids(day.posture_bonus_ids))
    more_posture = [
        _to_out(e, completed=done.get((e.id, "bonus"), False)) for e in posture_bonus
    ]
    glute_bonus = await _by_ids(session, _parse_ids(day.glute_bonus_ids))
    more_glutes = [
        _to_out(e, completed=done.get((e.id, "bonus"), False)) for e in glute_bonus
    ]
    posture_base = set(_parse_ids(day.posture_base_ids))
    glute_base = set(_parse_ids(day.muscle_exercise_ids))
    posture_catalog = await list_catalog(session, CAT_POSTURE)
    glute_catalog = await list_catalog(session, CAT_MUSCLE_GLUTES)
    extras = [
        DaySectionOut(
            key="more_posture",
            title="Еще осанку",
            kind="extra",
            required=False,
            can_add=bool(posture_catalog),
            options=more_posture,
        ),
        DaySectionOut(
            key="more_glutes",
            title="Еще попу",
            kind="extra",
            required=False,
            can_add=bool(glute_catalog),
            options=more_glutes,
        ),
    ]

    # Base: slot1–3 (+1 each), posture(n), neck(n), muscle(1)
    base_total = 0
    base_completed = 0
    for sec in sections:
        if sec.key in ("slot1", "slot2", "slot3"):
            if sec.exercises:
                base_total += 1
                if sec.exercises[0].completed:
                    base_completed += 1
        elif sec.key in ("posture_base", "neck", "muscle"):
            opts = sec.options or []
            base_total += len(opts)
            base_completed += sum(1 for e in opts if e.completed)

    bonus_completed = sum(1 for e in more_posture + more_glutes if e.completed)
    bonus_total = len(more_posture) + len(more_glutes)
    muscle_completed = sum(1 for e in muscle_outs if e.completed)

    return DayPlanOut(
        plan_date=plan_date,
        title="Тренировка дня",
        sections=sections,
        extras=extras,
        base_completed=base_completed,
        base_total=base_total,
        base_done=base_total > 0 and base_completed >= base_total,
        bonus_completed=bonus_completed,
        bonus_total=bonus_total,
        muscle_completed=muscle_completed,
        muscle_total=len(muscle_outs),
    )


async def add_extra(
    session: AsyncSession,
    user: User,
    *,
    kind: str,
    plan_date: date | None = None,
) -> DayPlanOut:
    """Добавить одно новое упражнение по кнопке «Еще осанку» / «Еще попу».

    Пока есть непоказанные — добавляем их. Когда круг закончился — начинаем список
    дополнительных заново (кнопка не отключается, пока в каталоге есть упражнения).
    """
    plan_date = plan_date or today_in_tz()
    day = await get_or_create_day_plan(session, user, plan_date)
    rng = random.Random(
        f"{user.id}:{plan_date.isoformat()}:extra:{kind}:"
        f"{len(_parse_ids(day.posture_bonus_ids))+len(_parse_ids(day.glute_bonus_ids))}"
    )

    if kind == "posture":
        category = CAT_POSTURE
        base_ids = set(_parse_ids(day.posture_base_ids))
        bonus_ids = _parse_ids(day.posture_bonus_ids)
    elif kind == "glutes":
        category = CAT_MUSCLE_GLUTES
        base_ids = set(_parse_ids(day.muscle_exercise_ids))
        bonus_ids = _parse_ids(day.glute_bonus_ids)
    else:
        raise ValueError("Unknown extra kind")

    catalog = await list_catalog(session, category)
    if not catalog:
        raise ValueError("В каталоге нет упражнений")

    shown = set(bonus_ids)
    unused = [e for e in catalog if e.id not in base_ids and e.id not in shown]
    if not unused:
        # Круг доп. упражнений закончился — начинаем сначала (не из базы дня)
        unused = [e for e in catalog if e.id not in base_ids] or list(catalog)
        bonus_ids = []

    chosen = rng.choice(unused)
    bonus_ids.append(chosen.id)
    if kind == "posture":
        day.posture_bonus_ids = _ids_to_str(bonus_ids)
    else:
        day.glute_bonus_ids = _ids_to_str(bonus_ids)

    await session.commit()
    return await build_day_plan(session, user, plan_date)


async def choose_variant(
    session: AsyncSession,
    user: User,
    *,
    slot: str,
    catalog_exercise_id: int,
    plan_date: date | None = None,
) -> DayPlanOut:
    plan_date = plan_date or today_in_tz()
    day = await get_or_create_day_plan(session, user, plan_date)
    result = await session.execute(
        select(CatalogExercise).where(CatalogExercise.id == catalog_exercise_id)
    )
    ex = result.scalar_one_or_none()
    if ex is None or not ex.is_active:
        raise ValueError("Exercise not found")

    if slot == "slot3":
        if ex.category != CAT_SLOT3:
            raise ValueError("Not a slot3 exercise")
        day.slot3_choice_id = ex.id
    elif slot == "neck":
        if ex.category != CAT_NECK:
            raise ValueError("Not a neck exercise")
        day.neck_choice_id = ex.id
    else:
        raise ValueError("Unknown slot")

    await session.commit()
    return await build_day_plan(session, user, plan_date)


async def _set_exercise_completion(
    session: AsyncSession,
    *,
    user_id: int,
    catalog_exercise_id: int,
    plan_date: date,
    block: str,
    completed: bool,
) -> None:
    result = await session.execute(
        select(UserCompletion).where(
            UserCompletion.user_id == user_id,
            UserCompletion.catalog_exercise_id == catalog_exercise_id,
            UserCompletion.plan_date == plan_date,
            UserCompletion.block == block,
        )
    )
    row = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None:
        session.add(
            UserCompletion(
                user_id=user_id,
                catalog_exercise_id=catalog_exercise_id,
                plan_date=plan_date,
                block=block,
                completed=completed,
                completed_at=now if completed else None,
            )
        )
    else:
        row.completed = completed
        row.completed_at = now if completed else None


async def toggle_completion(
    session: AsyncSession,
    user: User,
    *,
    completed: bool,
    block: str = "base",
    catalog_exercise_id: int | None = None,
    section: str | None = None,
    plan_date: date | None = None,
) -> DayPlanOut:
    plan_date = plan_date or today_in_tz()
    if block not in ("base", "bonus", "muscle"):
        raise ValueError("Invalid block")

    day = await get_or_create_day_plan(session, user, plan_date)

    if catalog_exercise_id is None:
        raise ValueError("catalog_exercise_id required")

    allowed: set[int] = set()
    if block == "base":
        for cat in (CAT_SLOT1, CAT_SLOT2, CAT_SLOT3):
            slot = await _fixed_slot(session, cat)
            if slot:
                allowed.add(slot.id)
        allowed.update(_parse_ids(day.posture_base_ids))
        allowed.update(_parse_ids(day.neck_exercise_ids))
        allowed.update(_parse_ids(day.muscle_exercise_ids))
    elif block == "bonus":
        allowed.update(_parse_ids(day.posture_bonus_ids))
        allowed.update(_parse_ids(day.glute_bonus_ids))
    else:
        allowed.update(_parse_ids(day.muscle_exercise_ids))

    if catalog_exercise_id not in allowed:
        raise ValueError("Exercise not in today's plan for this block")

    await _set_exercise_completion(
        session,
        user_id=user.id,
        catalog_exercise_id=catalog_exercise_id,
        plan_date=plan_date,
        block=block,
        completed=completed,
    )
    await session.commit()
    return await build_day_plan(session, user, plan_date)


async def user_day_stats(session: AsyncSession, user: User, plan_date: date | None = None) -> DaySummary:
    plan_date = plan_date or today_in_tz()
    out = await build_day_plan(session, user, plan_date)
    return DaySummary(
        plan_date=out.plan_date,
        title=out.title,
        completed_count=out.base_completed,
        total_count=out.base_total,
        done=out.base_done,
    )


async def month_success(
    session: AsyncSession,
    user: User,
    *,
    year: int | None = None,
    month: int | None = None,
) -> MonthSuccessOut:
    today = today_in_tz()
    year = year or today.year
    month = month or today.month
    if month < 1 or month > 12:
        raise ValueError("Invalid month")

    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    days_in_month = (end - start).days

    plans_result = await session.execute(
        select(UserDayPlan).where(
            UserDayPlan.user_id == user.id,
            UserDayPlan.plan_date >= start,
            UserDayPlan.plan_date < end,
        )
    )
    plans = {p.plan_date: p for p in plans_result.scalars().all()}

    comps_result = await session.execute(
        select(UserCompletion).where(
            UserCompletion.user_id == user.id,
            UserCompletion.plan_date >= start,
            UserCompletion.plan_date < end,
            UserCompletion.completed.is_(True),
        )
    )
    completions = list(comps_result.scalars().all())
    base_done_map: dict[date, set[int]] = {}
    bonus_ids_map: dict[date, set[int]] = {}
    for row in completions:
        if row.block in ("base", "muscle"):
            base_done_map.setdefault(row.plan_date, set()).add(row.catalog_exercise_id)
        elif row.block == "bonus":
            bonus_ids_map.setdefault(row.plan_date, set()).add(row.catalog_exercise_id)

    logs_result = await session.execute(
        select(ActivityLog)
        .where(
            ActivityLog.user_id == user.id,
            ActivityLog.log_date >= start,
            ActivityLog.log_date < end,
        )
        .order_by(ActivityLog.log_date.desc(), ActivityLog.id.desc())
    )
    month_logs = list(logs_result.scalars().all())
    log_kinds_map: dict[date, list[str]] = {}
    kind_order = ("strength", "face", "note")
    for row in month_logs:
        kinds = log_kinds_map.setdefault(row.log_date, [])
        if row.kind not in kinds:
            kinds.append(row.kind)
    for d, kinds in log_kinds_map.items():
        log_kinds_map[d] = [k for k in kind_order if k in kinds] + [
            k for k in kinds if k not in kind_order
        ]

    # Fixed slots are the same for all days — resolve once
    slot_ids: list[int] = []
    for cat in (CAT_SLOT1, CAT_SLOT2, CAT_SLOT3):
        ex = await _fixed_slot(session, cat)
        if ex:
            slot_ids.append(ex.id)

    days_out: list[SuccessDayOut] = []
    base_closed = 0
    bonus_total = 0
    for day_num in range(1, days_in_month + 1):
        d = date(year, month, day_num)
        plan = plans.get(d)
        bonus_count = len(bonus_ids_map.get(d, set()))
        base_done = False
        if plan is not None:
            needed = list(slot_ids)
            needed.extend(_parse_ids(plan.posture_base_ids))
            needed.extend(_parse_ids(plan.neck_exercise_ids))
            needed.extend(_parse_ids(plan.muscle_exercise_ids))
            needed_u: list[int] = []
            seen: set[int] = set()
            for i in needed:
                if i not in seen:
                    seen.add(i)
                    needed_u.append(i)
            done_ids = base_done_map.get(d, set())
            base_done = bool(needed_u) and all(i in done_ids for i in needed_u)
        if base_done:
            base_closed += 1
            bonus_total += bonus_count
        days_out.append(
            SuccessDayOut(
                date=d,
                base_done=base_done,
                bonus_count=bonus_count,
                log_kinds=log_kinds_map.get(d, []),
            )
        )

    months_ru = (
        "",
        "январь",
        "февраль",
        "март",
        "апрель",
        "май",
        "июнь",
        "июль",
        "август",
        "сентябрь",
        "октябрь",
        "ноябрь",
        "декабрь",
    )
    label = f"{months_ru[month]} {year}"

    return MonthSuccessOut(
        year=year,
        month=month,
        label=label,
        days_in_month=days_in_month,
        base_closed_days=base_closed,
        bonus_total=bonus_total,
        days=days_out,
        logs=[_activity_out(r) for r in month_logs],
    )


def _activity_out(row: ActivityLog) -> ActivityLogOut:
    return ActivityLogOut(
        id=row.id,
        log_date=row.log_date,
        kind=row.kind,
        kind_label=ACTIVITY_KINDS.get(row.kind, row.kind),
        comment=row.comment or "",
    )


async def day_success(
    session: AsyncSession, user: User, plan_date: date
) -> DaySuccessOut:
    result = await session.execute(
        select(UserDayPlan).where(
            UserDayPlan.user_id == user.id, UserDayPlan.plan_date == plan_date
        )
    )
    plan = result.scalar_one_or_none()
    done = await _completions_map(session, user.id, plan_date)

    base_exercises: list[CatalogExerciseOut] = []
    bonus_exercises: list[CatalogExerciseOut] = []
    base_total = 0
    base_completed = 0
    base_done = False

    if plan is not None:
        needed: list[int] = []
        for cat in (CAT_SLOT1, CAT_SLOT2, CAT_SLOT3):
            ex = await _fixed_slot(session, cat)
            if ex:
                needed.append(ex.id)
        needed.extend(_parse_ids(plan.posture_base_ids))
        needed.extend(_parse_ids(plan.neck_exercise_ids))
        needed.extend(_parse_ids(plan.muscle_exercise_ids))
        seen: set[int] = set()
        base_ids: list[int] = []
        for i in needed:
            if i not in seen:
                seen.add(i)
                base_ids.append(i)
        base_items = await _by_ids(session, base_ids)
        for ex in base_items:
            completed = done.get((ex.id, "base"), False) or done.get((ex.id, "muscle"), False)
            base_exercises.append(_to_out(ex, completed=completed))
            base_total += 1
            if completed:
                base_completed += 1
        base_done = base_total > 0 and base_completed >= base_total

        bonus_ids = list(
            dict.fromkeys(
                _parse_ids(plan.posture_bonus_ids) + _parse_ids(plan.glute_bonus_ids)
            )
        )
        # Also include any completed bonus not in frozen lists (edge cases)
        for (ex_id, block), ok in done.items():
            if block == "bonus" and ok and ex_id not in bonus_ids:
                bonus_ids.append(ex_id)
        bonus_items = await _by_ids(session, bonus_ids)
        for ex in bonus_items:
            completed = done.get((ex.id, "bonus"), False)
            if completed:
                bonus_exercises.append(_to_out(ex, completed=True))

    logs_result = await session.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == user.id, ActivityLog.log_date == plan_date)
        .order_by(ActivityLog.id.desc())
    )
    logs = [_activity_out(r) for r in logs_result.scalars().all()]

    return DaySuccessOut(
        date=plan_date,
        base_done=base_done,
        base_completed=base_completed,
        base_total=base_total,
        base_exercises=base_exercises,
        bonus_exercises=bonus_exercises,
        logs=logs,
        activity_kinds=[{"id": k, "label": v} for k, v in ACTIVITY_KINDS.items()],
    )


async def add_activity_log(
    session: AsyncSession,
    user: User,
    *,
    log_date: date,
    kind: str,
    comment: str,
) -> DaySuccessOut:
    if kind not in ACTIVITY_KINDS:
        raise ValueError("Unknown activity kind")
    text = (comment or "").strip()
    if not text:
        raise ValueError("Напиши комментарий")
    session.add(
        ActivityLog(
            user_id=user.id,
            log_date=log_date,
            kind=kind,
            comment=text,
        )
    )
    await session.commit()
    return await day_success(session, user, log_date)


async def delete_activity_log(
    session: AsyncSession, user: User, log_id: int
) -> DaySuccessOut:
    result = await session.execute(
        select(ActivityLog).where(ActivityLog.id == log_id, ActivityLog.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError("Запись не найдена")
    log_date = row.log_date
    await session.delete(row)
    await session.commit()
    return await day_success(session, user, log_date)


async def list_users_needing_reminder(
    session: AsyncSession, plan_date: date | None = None
) -> list[tuple[User, DayPlanOut]]:
    plan_date = plan_date or today_in_tz()
    # need at least slot1 in catalog
    if not await list_catalog(session, CAT_SLOT1):
        return []

    result = await session.execute(select(User))
    users = result.scalars().all()
    needing: list[tuple[User, DayPlanOut]] = []
    for user in users:
        out = await build_day_plan(session, user, plan_date)
        if out.base_total == 0:
            continue
        if not out.base_done:
            needing.append((user, out))
    return needing
