from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import validate_init_data
from app.config import get_settings
from app.db import get_session
from app.models import CATEGORY_LABELS
from app.schemas import (
    ActivityLogIn,
    CatalogAddIn,
    CatalogExerciseOut,
    CatalogUpdateIn,
    ChooseIn,
    CompleteBaseIn,
    DayPlanOut,
    DaySuccessOut,
    DaySummary,
    ExtraIn,
    MonthSuccessOut,
    ToggleProgressIn,
    UserOut,
)
from app import services

router = APIRouter(prefix="/api")


async def current_user(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    session: AsyncSession = Depends(get_session),
):
    if not x_telegram_init_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Telegram-Init-Data required")

    data = validate_init_data(x_telegram_init_data)
    tg = data["user"]
    user = await services.upsert_user(
        session,
        telegram_id=tg["id"],
        username=tg.get("username"),
        first_name=tg.get("first_name"),
        last_name=tg.get("last_name"),
    )
    return user


def require_admin(user) -> None:
    if not services.is_admin_user(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


def catalog_out(row) -> CatalogExerciseOut:
    return CatalogExerciseOut(
        id=row.id,
        category=row.category,
        name=row.name,
        description=row.description,
        video_url=row.video_url,
        sort_order=row.sort_order,
        is_active=row.is_active,
    )


@router.get("/me", response_model=UserOut)
async def me(user=Depends(current_user)):
    return UserOut(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        is_admin=services.is_admin_user(user),
    )


@router.get("/meta/categories")
async def categories(user=Depends(current_user)):
    require_admin(user)
    return [{"id": k, "label": v} for k, v in CATEGORY_LABELS.items()]


@router.get("/plan/today", response_model=DayPlanOut)
async def plan_today(user=Depends(current_user), session: AsyncSession = Depends(get_session)):
    return await services.build_day_plan(session, user)


@router.get("/plan/{plan_date}", response_model=DayPlanOut)
async def plan_by_date(
    plan_date: date,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await services.build_day_plan(session, user, plan_date)


@router.post("/extra", response_model=DayPlanOut)
async def add_extra(
    payload: ExtraIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await services.add_extra(session, user, kind=payload.kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/choose", response_model=DayPlanOut)
async def choose(
    payload: ChooseIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await services.choose_variant(
            session,
            user,
            slot=payload.slot,
            catalog_exercise_id=payload.catalog_exercise_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/progress", response_model=DayPlanOut)
async def toggle_progress(
    payload: ToggleProgressIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await services.toggle_completion(
            session,
            user,
            catalog_exercise_id=payload.catalog_exercise_id,
            section=payload.section,
            block=payload.block,
            completed=payload.completed,
            plan_date=payload.plan_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/progress/complete-base", response_model=DayPlanOut)
async def complete_base(
    payload: CompleteBaseIn = CompleteBaseIn(),
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await services.complete_base_circle(
            session,
            user,
            plan_date=payload.plan_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/success/month", response_model=MonthSuccessOut)
async def success_month(
    year: int | None = None,
    month: int | None = None,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await services.month_success(session, user, year=year, month=month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/success/day/{plan_date}", response_model=DaySuccessOut)
async def success_day(
    plan_date: date,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    return await services.day_success(session, user, plan_date)


@router.post("/success/logs", response_model=DaySuccessOut)
async def create_activity_log(
    payload: ActivityLogIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await services.add_activity_log(
            session,
            user,
            log_date=payload.log_date,
            kind=payload.kind,
            comment=payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/success/logs/{log_id}", response_model=DaySuccessOut)
async def remove_activity_log(
    log_id: int,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await services.delete_activity_log(session, user, log_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/summary/today", response_model=DaySummary)
async def summary_today(user=Depends(current_user), session: AsyncSession = Depends(get_session)):
    return await services.user_day_stats(session, user)


@router.get("/catalog", response_model=list[CatalogExerciseOut])
async def catalog_list(
    category: str | None = None,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_admin(user)
    rows = await services.list_catalog(session, category, active_only=False)
    return [catalog_out(r) for r in rows]


@router.post("/catalog", response_model=CatalogExerciseOut)
async def catalog_add(
    payload: CatalogAddIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_admin(user)
    if payload.category not in CATEGORY_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category. Use: {', '.join(CATEGORY_LABELS)}",
        )
    row = await services.add_catalog_exercise(
        session,
        category=payload.category,
        name=payload.name,
        description=payload.description,
        video_url=payload.video_url,
        sort_order=payload.sort_order,
    )
    return catalog_out(row)


@router.patch("/catalog/{exercise_id}", response_model=CatalogExerciseOut)
async def catalog_update(
    exercise_id: int,
    payload: CatalogUpdateIn,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_admin(user)
    if payload.category is not None and payload.category not in CATEGORY_LABELS:
        raise HTTPException(status_code=400, detail="Unknown category")
    try:
        row = await services.update_catalog_exercise(
            session,
            exercise_id,
            category=payload.category,
            name=payload.name,
            description=payload.description,
            video_url=payload.video_url,
            sort_order=payload.sort_order,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return catalog_out(row)


@router.delete("/catalog/{exercise_id}")
async def catalog_delete(
    exercise_id: int,
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_admin(user)
    try:
        await services.delete_catalog_exercise(session, exercise_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/catalog/reload-seed")
async def catalog_reload_seed(
    user=Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    require_admin(user)
    n = await services.reload_catalog_from_seed(session)
    return {"ok": True, "loaded": n}
