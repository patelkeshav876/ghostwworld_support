import random
import string
import html
from typing import Optional

def generate_ticket_id(prefix: str = "TK") -> str:
    """Generate a clean human-readable ticket ID, e.g. TK-7942"""
    digits = "".join(random.choices(string.digits, k=4))
    letters = "".join(random.choices(string.ascii_uppercase, k=2))
    return f"{prefix}-{letters}{digits}"

def escape_html(text: Optional[str]) -> str:
    """Escapes string safely for HTML parse mode"""
    if text is None:
        return ""
    return html.escape(str(text))

def format_user_mention(user_id: int, name: str, username: Optional[str] = None) -> str:
    clean_name = escape_html(name)
    if username:
        return f'<a href="tg://user?id={user_id}">{clean_name}</a> (@{escape_html(username)})'
    return f'<a href="tg://user?id={user_id}">{clean_name}</a>'

def parse_deep_link(args_str: str) -> dict:
    """
    Parses deep links like:
    /start webapp
    /start bot_trading
    /start sub_issue
    /start ticket_TK-1234
    """
    if not args_str:
        return {"action": "default", "param": None}
    
    parts = args_str.strip().split("_", 1)
    if len(parts) == 1:
        return {"action": parts[0], "param": None}
    return {"action": parts[0], "param": parts[1]}

async def safe_edit_message(query, text: str, reply_markup=None, parse_mode: str = "HTML", disable_web_page_preview: bool = True):
    """
    Safely edits a message regardless of whether it's a photo message or text message.
    If it's a photo message and the caption fits (<= 1024 chars), edits the caption.
    Otherwise, deletes the message and sends a new text message.
    """
    if query.message and query.message.photo:
        if len(text) <= 1024:
            try:
                await query.edit_message_caption(
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                return
            except Exception:
                pass
        
        # If caption edit fails or text exceeds 1024 chars, delete photo message and send text
        try:
            await query.message.delete()
        except Exception:
            pass
            
        await query.message.chat.send_message(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
    else:
        try:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                await query.message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )

