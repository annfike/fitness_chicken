"""Channel membership checks for private video channel."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus

from app.config import get_settings

logger = logging.getLogger(__name__)

_MEMBER_OK = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}


def channel_configured() -> bool:
    s = get_settings()
    return bool(s.channel_id.strip() and s.channel_invite_link.strip())


async def is_channel_member(bot: Bot, user_id: int) -> bool | None:
    """True / False if check ok; None if channel not configured or API error."""
    settings = get_settings()
    chat_id = settings.channel_id.strip()
    if not chat_id:
        return None
    try:
        # numeric private channel: -100XXXXXXXXXX
        target: int | str = int(chat_id) if chat_id.lstrip("-").isdigit() else chat_id
        member = await bot.get_chat_member(chat_id=target, user_id=user_id)
        status = member.status
        status_val = getattr(status, "value", status)
        ok = status in _MEMBER_OK or status_val in {s.value for s in _MEMBER_OK}
        # Restricted members may be in chat but not "is_member"
        if status_val == ChatMemberStatus.RESTRICTED.value:
            ok = bool(getattr(member, "is_member", True))
        logger.info(
            "channel membership user=%s chat=%s status=%s subscribed=%s",
            user_id,
            target,
            status_val,
            ok,
        )
        return ok
    except Exception:
        logger.exception("getChatMember failed for user=%s channel=%s", user_id, chat_id)
        return None


async def membership_payload(bot: Bot | None, user_id: int) -> dict:
    settings = get_settings()
    invite = settings.channel_invite_link.strip()
    if not settings.channel_id.strip():
        return {"required": False, "subscribed": True, "invite_link": invite or None}
    if bot is None:
        return {"required": True, "subscribed": False, "invite_link": invite or None}
    subscribed = await is_channel_member(bot, user_id)
    if subscribed is None:
        # Fail open for video if check broken, but still return invite if set
        return {
            "required": True,
            "subscribed": True,
            "invite_link": invite or None,
            "check_failed": True,
        }
    return {
        "required": True,
        "subscribed": subscribed,
        "invite_link": invite or None,
    }
