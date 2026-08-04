from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.channel import channel_configured, membership_payload
from app.config import get_settings, webapp_public_url
from app.db import SessionLocal, resolve_sqlite_file
from app import services

logger = logging.getLogger(__name__)

bot: Bot | None = None
dp = Dispatcher()
scheduler = AsyncIOScheduler()


def _require_admin(message: Message) -> bool:
    settings = get_settings()
    if settings.admin_id_set and message.from_user.id not in settings.admin_id_set:
        return False
    return True


def resolve_sqlite_path() -> Path | None:
    return resolve_sqlite_file()


def webapp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть план на день",
                    web_app=WebAppInfo(url=webapp_public_url()),
                )
            ],
        ]
    )


async def sync_menu_button(bot_instance: Bot, chat_id: int | None = None) -> None:
    """Push WEBAPP_URL from .env into Telegram Menu Button (default or per-chat)."""
    url = webapp_public_url()
    await bot_instance.set_chat_menu_button(
        chat_id=chat_id,
        menu_button=MenuButtonWebApp(text="Fitness Chicken", web_app=WebAppInfo(url=url)),
    )
    where = f"chat {chat_id}" if chat_id is not None else "default"
    logger.info("Menu button synced (%s) -> %s", where, url)


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with SessionLocal() as session:
        await services.upsert_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

    if bot is not None:
        try:
            await sync_menu_button(bot, chat_id=message.chat.id)
        except Exception:
            logger.exception("Failed to sync menu button for chat %s", message.chat.id)

    await message.answer(
        "Привет, спортивная курочка!\n\n"
        "Потрать всего 10 минут для своей красоты.\n"
        "Базовый круг - 10 упражнений по 1 (одной!) минуте.\n"
        "Для отличниц - доп. упражнения.\n"
        "Три раза в день напомню, если база ещё не закрыта.\n\n"
        "Команды:\n"
        "/today — прогресс за сегодня\n"
        "/start — перезапуск бота\n"
        "/backup — скачать файл БД (админ)\n"
        "/export_catalog — каталог в JSON (админ)",
        reply_markup=webapp_keyboard(),
    )

    if bot is not None and channel_configured():
        try:
            status = await membership_payload(bot, message.from_user.id)
            if status.get("required") and not status.get("subscribed"):
                invite = status.get("invite_link")
                if invite:
                    kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="Вступить в канал с видео", url=invite)]
                        ]
                    )
                    await message.answer(
                        "Видео к упражнениям лежат в закрытом канале.\n"
                        "Нажми кнопку ниже, вступи — и ролики откроются.",
                        reply_markup=kb,
                    )
        except Exception:
            logger.exception("Failed to send channel invite on /start")


@dp.message(Command("today"))
async def cmd_today(message: Message) -> None:
    async with SessionLocal() as session:
        user = await services.upsert_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        summary = await services.user_day_stats(session, user)

    if summary.total_count == 0:
        await message.answer("Каталог упражнений ещё пуст. Админ: /add_ex")
        return

    if summary.done:
        text = (
            f"✅ Базовый круг закрыт: {summary.completed_count}/{summary.total_count}\n"
            f"Но не возбраняется сделать больше!"
        )
    else:
        text = (
            f"📋 Базовый круг: {summary.completed_count}/{summary.total_count}\n"
            f"Открой приложение и доведи дело до конца, звезда моя."
        )
    await message.answer(text, reply_markup=webapp_keyboard())


def _normalize_video_url(value: str) -> str:
    value = value.strip()
    if value.startswith("t.me/"):
        return f"https://{value}"
    return value


def _is_url(value: str) -> bool:
    v = value.strip().lower()
    return v.startswith(("http://", "https://", "t.me/"))


@dp.message(Command("add_ex"))
async def cmd_add_ex(message: Message) -> None:
    """
    /add_ex category|Название|описание|https://t.me/...
    """
    from app.models import CATEGORY_LABELS

    if not _require_admin(message):
        await message.answer("Только для админов.")
        return

    raw = (message.text or "").partition(" ")[2].strip()
    if not raw:
        cats = ", ".join(CATEGORY_LABELS)
        await message.answer(
            "Формат:\n"
            "/add_ex category|Название|описание|ссылка\n\n"
            f"Категории: {cats}\n\n"
            "Пример:\n"
            "/add_ex posture|Лодочка|Лёжа на животе|https://t.me/channel/12"
        )
        return

    bits = [b.strip() for b in raw.split("|")]
    if len(bits) < 2:
        await message.answer("Нужно минимум: category|Название")
        return

    category, name = bits[0], bits[1]
    if category not in CATEGORY_LABELS:
        await message.answer("Неизвестная категория: " + category)
        return

    description = None
    video_url = None
    for bit in bits[2:]:
        if _is_url(bit):
            video_url = _normalize_video_url(bit)
        elif bit:
            description = bit

    async with SessionLocal() as session:
        row = await services.add_catalog_exercise(
            session,
            category=category,
            name=name,
            description=description,
            video_url=video_url,
        )
    await message.answer(
        f"Добавлено #{row.id} [{row.category}]: {row.name}" + (" 🎬" if row.video_url else "")
    )


@dp.message(Command("list_ex"))
async def cmd_list_ex(message: Message) -> None:
    """/list_ex [category]"""
    from app.models import CATEGORY_LABELS

    if not _require_admin(message):
        await message.answer("Только для админов.")
        return

    category = (message.text or "").partition(" ")[2].strip() or None
    if category and category not in CATEGORY_LABELS:
        await message.answer("Неизвестная категория.")
        return

    async with SessionLocal() as session:
        rows = await services.list_catalog(session, category, active_only=False)

    if not rows:
        await message.answer("Каталог пуст.")
        return

    lines = [f"#{r.id} [{r.category}] {r.name}" for r in rows[:40]]
    extra = f"\n… ещё {len(rows) - 40}" if len(rows) > 40 else ""
    await message.answer("Каталог:\n" + "\n".join(lines) + extra)


@dp.message(Command("backup"))
async def cmd_backup(message: Message) -> None:
    """Send SQLite database file to admin via Telegram."""
    if not _require_admin(message):
        await message.answer("Только для админов.")
        return

    path = resolve_sqlite_path()
    if path is None:
        await message.answer("Бэкап поддерживается только для SQLite.")
        return
    if not path.exists():
        await message.answer(f"Файл БД не найден: {path}")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    await message.answer_document(
        FSInputFile(path, filename=f"fitness_{stamp}.db"),
        caption="Бэкап базы данных. Сохрани файл у себя.",
    )


@dp.message(Command("export_catalog"))
async def cmd_export_catalog(message: Message) -> None:
    """Send catalog as JSON (same shape as catalog_seed.json)."""
    if not _require_admin(message):
        await message.answer("Только для админов.")
        return

    async with SessionLocal() as session:
        rows = await services.list_catalog(session, category=None, active_only=False)

    data = [
        {
            "category": r.category,
            "name": r.name or "",
            "description": r.description,
            "video_url": r.video_url,
            "sort_order": int(r.sort_order or 0),
        }
        for r in rows
    ]
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    await message.answer_document(
        BufferedInputFile(payload, filename=f"catalog_seed_{stamp}.json"),
        caption=f"Каталог: {len(data)} упражнений",
    )


async def send_progress_reminders() -> None:
    """Remind users who haven't finished the base circle today."""
    if bot is None:
        return

    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz).date()

    async with SessionLocal() as session:
        needing = await services.list_users_needing_reminder(session, today)

    logger.info("Reminder run: %s users need nudge for %s", len(needing), today)

    for user, plan_out in needing:
        pending_bits: list[str] = []
        for sec in plan_out.sections:
            if sec.key == "posture_bonus":
                continue
            if sec.kind == "checklist":
                for e in sec.options:
                    if not e.completed:
                        pending_bits.append(e.name or sec.title)
            elif sec.kind == "fixed":
                for e in sec.exercises:
                    if not e.completed:
                        pending_bits.append(e.name or sec.title)
            else:
                for e in sec.exercises:
                    if not e.completed:
                        pending_bits.append(e.name)
        pending_preview = ", ".join(pending_bits[:5])
        if len(pending_bits) > 5:
            pending_preview += "…"

        text = (
            f"⏰ Напоминание: базовый круг\n\n"
            f"Сделано: {plan_out.base_completed}/{plan_out.base_total}\n"
            f"Осталось: {pending_preview or 'открыть приложение'}\n\n"
            f"После базы можно ещё осанку или попу."
        )
        try:
            await bot.send_message(user.telegram_id, text, reply_markup=webapp_keyboard())
        except Exception:
            logger.exception("Failed to remind user %s", user.telegram_id)


def setup_scheduler() -> None:
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    scheduler.remove_all_jobs()

    for i, hhmm in enumerate(settings.reminder_time_list):
        hour_s, minute_s = hhmm.split(":")
        scheduler.add_job(
            send_progress_reminders,
            CronTrigger(hour=int(hour_s), minute=int(minute_s), timezone=tz),
            id=f"reminder_{i}_{hhmm}",
            replace_existing=True,
        )
        logger.info("Scheduled reminder at %s (%s)", hhmm, settings.timezone)

    if not scheduler.running:
        scheduler.start()


async def start_bot() -> None:
    global bot
    settings = get_settings()
    if not settings.bot_token or settings.bot_token.startswith("123456"):
        logger.warning("BOT_TOKEN not set — bot polling disabled")
        return

    bot = Bot(token=settings.bot_token)
    try:
        await sync_menu_button(bot)
    except Exception:
        logger.exception("Failed to set menu button")
    setup_scheduler()
    logger.info("Starting bot polling…")
    await dp.start_polling(bot)


async def stop_bot() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
    if bot is not None:
        await bot.session.close()
