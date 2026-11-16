import logging
from telegram import Update
from telegram.ext import ContextTypes
from database import db
from keyboards import get_main_menu_keyboard
from utils.helpers import escape_html, parse_deep_link
from config import config

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    # Ignore group chats for /start unless intended
    if chat.type != "private":
        return

    # Register/update user in database
    db_user = await db.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    if db_user and db_user.get("is_banned"):
        await update.message.reply_text(
            "🚫 <b>Access Restricted</b>\nYour account has been suspended from using the support portal.",
            parse_mode="HTML"
        )
        return

    # Check for active ticket
    active_ticket = await db.get_active_ticket_for_user(user.id)
    
    # Process deep links
    deep_link_args = context.args[0] if context.args else ""
    parsed = parse_deep_link(deep_link_args)
    action = parsed.get("action")
    
    welcome_text = (
        f"👋 <b>Welcome, {escape_html(user.first_name)}!</b>\n\n"
        f"I am the unified <b>Help & Support Assistant</b> for our Web App and bot ecosystem.\n\n"
        f"✨ <i>How can we assist you today?</i>\n"
        f"• 💬 <b>Ask a Question:</b> Connect directly with our support specialists.\n"
        f"• 💳 <b>Subscriptions & Billing:</b> Verify transactions, request upgrades or refunds.\n"
        f"• 🚨 <b>Complaints:</b> Submit formal concerns for priority escalation.\n"
        f"• 🤝 <b>Join Our Family:</b> Discover our VIP community, official updates, and perks.\n\n"
    )

    if active_ticket:
        welcome_text += (
            f"⚡ <i>You currently have an active ticket:</i> <code>{active_ticket['ticket_id']}</code>\n"
            f"Status: <b>{active_ticket['status']}</b>. You can reply anytime directly here to send messages to our agents."
        )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard(has_active_ticket=bool(active_ticket)),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    active_ticket = await db.get_active_ticket_for_user(user.id)
    
    text = (
        f"🏠 <b>Main Support Hub</b>\n\n"
        f"Select an option below to proceed with your query or connect with our support team."
    )
    if active_ticket:
        text += f"\n\n📌 <b>Active Ticket:</b> <code>{active_ticket['ticket_id']}</code> ({active_ticket['status']})"
        
    await query.edit_message_text(
        text,
        reply_markup=get_main_menu_keyboard(has_active_ticket=bool(active_ticket)),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
