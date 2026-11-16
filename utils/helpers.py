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
