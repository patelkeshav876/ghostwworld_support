import logging
from typing import Optional
from telegram import Bot

logger = logging.getLogger(__name__)

async def create_ticket_topic(bot: Bot, chat_id: int, title: str, icon_color: int = 0x6FB9F0) -> Optional[int]:
    """
    Creates a dedicated Forum Topic for a ticket in the Admin Supergroup.
    Returns the message_thread_id of the topic, or None if failed/topics disabled.
    """
    try:
        topic = await bot.create_forum_topic(
            chat_id=chat_id,
            name=title[:120], # Telegram limit 128 chars
            icon_color=icon_color
        )
        return topic.message_thread_id
    except Exception as e:
        logger.warning(f"Could not create forum topic in chat {chat_id}: {e}")
        return None

async def close_ticket_topic(bot: Bot, chat_id: int, message_thread_id: int) -> bool:
    """Closes a forum topic when a ticket is resolved"""
    try:
        await bot.close_forum_topic(chat_id=chat_id, message_thread_id=message_thread_id)
        return True
    except Exception as e:
        logger.warning(f"Could not close forum topic {message_thread_id}: {e}")
        return False

async def reopen_ticket_topic(bot: Bot, chat_id: int, message_thread_id: int) -> bool:
    """Reopens a forum topic if a user writes back on a resolved ticket"""
    try:
        await bot.reopen_forum_topic(chat_id=chat_id, message_thread_id=message_thread_id)
        return True
    except Exception as e:
        logger.warning(f"Could not reopen forum topic {message_thread_id}: {e}")
        return False

async def try_set_reaction(bot: Bot, chat_id: int, message_id: int, emoji: str = "👍") -> None:
    """
    Attempts to set an emoji reaction using modern Telegram API.
    Fails gracefully if bot token or Telegram library version doesn't support reactions.
    """
    try:
        if hasattr(bot, "_post"):
            await bot._post(
                "setMessageReaction",
                data={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reaction": [{"type": "emoji", "emoji": emoji}],
                    "is_big": False
                }
            )
    except Exception as e:
        logger.debug(f"Reaction could not be set: {e}")
