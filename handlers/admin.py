import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from keyboards import get_csat_keyboard
from utils.helpers import escape_html, format_user_mention
from utils.telegram_features import close_ticket_topic, try_set_reaction
from config import config

logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    return user_id in config.SUPER_ADMINS

# --- Staff Message Relay (Admin Supergroup -> User) ---

async def handle_admin_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or update.effective_chat.id != config.ADMIN_GROUP_ID:
        return

    # Don't relay bot's own messages
    if message.from_user.is_bot:
        return

    # Check if message is in a forum topic
    thread_id = message.message_thread_id
    ticket = None
    
    if thread_id:
        ticket = await db.get_ticket_by_topic_id(thread_id)

    # If not in topic or topic not found, check if it's a quote reply to a forwarded message
    if not ticket and message.reply_to_message:
        # Check if the replied message contains a ticket ID pattern
        replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        import re
        match = re.search(r"\[(TK-[A-Z0-9]+|CMP-[A-Z0-9]+)\]", replied_text)
        if match:
            ticket = await db.get_ticket(match.group(1))

    if not ticket:
        return

    # If ticket is already resolved, don't relay or notify admin
    if ticket["status"] in ("RESOLVED", "CLOSED"):
        await message.reply_text("⚠️ This ticket is marked as RESOLVED. Use /reopen or create a new one.")
        return

    user_id = ticket["user_id"]
    ticket_id = ticket["ticket_id"]
    
    reply_text = message.text or message.caption or ""
    media_type = None
    media_file_id = None
    
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
    elif message.voice:
        media_type = "voice"
        media_file_id = message.voice.file_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id

    # Save to history
    await db.add_ticket_message(
        ticket_id=ticket_id,
        sender_type="ADMIN",
        sender_id=message.from_user.id,
        text=reply_text,
        media_type=media_type,
        media_file_id=media_file_id
    )

    # Update ticket status to IN_PROGRESS
    if ticket["status"] == "OPEN":
        await db.update_ticket_status(ticket_id, "IN_PROGRESS")

    # Send message to user
    header = f"🛡️ <b>Support Specialist</b> <i>(Ticket #{ticket_id})</i>:\n\n"
    
    try:
        if media_type == "photo":
            await context.bot.send_photo(
                chat_id=user_id,
                photo=media_file_id,
                caption=header + escape_html(reply_text),
                parse_mode="HTML"
            )
        elif media_type == "document":
            await context.bot.send_document(
                chat_id=user_id,
                document=media_file_id,
                caption=header + escape_html(reply_text),
                parse_mode="HTML"
            )
        elif media_type == "voice":
            await context.bot.send_voice(
                chat_id=user_id,
                voice=media_file_id,
                caption=header,
                parse_mode="HTML"
            )
        elif media_type == "video":
            await context.bot.send_video(
                chat_id=user_id,
                video=media_file_id,
                caption=header + escape_html(reply_text),
                parse_mode="HTML"
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=header + escape_html(reply_text),
                parse_mode="HTML"
            )
            
        await try_set_reaction(context.bot, message.chat.id, message.message_id, "🚀")
    except Exception as e:
        logger.error(f"Failed to relay admin message to user {user_id}: {e}")
        await message.reply_text(f"❌ Could not deliver to user: {e}")

# --- Admin Commands ---

async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return
        
    ticket = None
    if message.message_thread_id:
        ticket = await db.get_ticket_by_topic_id(message.message_thread_id)
        
    if not ticket and context.args:
        ticket = await db.get_ticket(context.args[0].strip())
        
    if not ticket:
        await message.reply_text("Usage: Send /close inside a ticket topic, or <code>/close TK-XXXX</code>", parse_mode="HTML")
        return

    await resolve_ticket_flow(context.bot, ticket, closed_by_admin=True)
    await message.reply_text(f"✅ Ticket <code>{ticket['ticket_id']}</code> marked as RESOLVED.", parse_mode="HTML")

async def resolve_ticket_flow(bot, ticket: dict, closed_by_admin: bool = True):
    ticket_id = ticket["ticket_id"]
    user_id = ticket["user_id"]
    topic_id = ticket.get("forum_topic_id")
    
    await db.update_ticket_status(ticket_id, "RESOLVED")
    
    # Close forum topic if exists
    if topic_id and config.ADMIN_GROUP_ID != 0:
        await close_ticket_topic(bot, config.ADMIN_GROUP_ID, topic_id)
        
    # Notify user with CSAT rating keyboard
    resolution_text = (
        f"🎉 <b>Ticket #{ticket_id} Resolved!</b>\n\n"
        f"Our team has marked your issue as resolved. "
        f"If you need anything else, you can open a new ticket at any time.\n\n"
        f"<b>How would you rate our support?</b>"
    )
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=resolution_text,
            reply_markup=get_csat_keyboard(ticket_id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to send resolution prompt to user {user_id}: {e}")

# --- Admin Callback Queries ---

async def admin_resolve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ticket_id = query.data.replace("adm_resolve_", "")
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        await query.answer("Ticket not found.")
        return

    await resolve_ticket_flow(context.bot, ticket)
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Resolved", callback_data="none")]
    ]))

async def admin_ban_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.replace("adm_ban_", ""))
    await db.set_user_banned(user_id, True)
    await query.answer(f"User {user_id} has been banned.", show_alert=True)

async def admin_sub_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    sub_id = int(parts[3])
    user_id = int(parts[4])
    
    await db.update_subscription_status(sub_id, "APPROVED", admin_notes="Approved via Telegram Bot")
    await db.set_user_vip(user_id, True)
    
    # Update admin message
    await query.edit_message_caption(
        caption=(query.message.caption or "") + "\n\n<b>STATUS:</b> ✅ APPROVED by Admin",
        parse_mode="HTML"
    )
    
    # Notify user
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "🎉 <b>Subscription Approved & Activated!</b>\n\n"
                "Your payment proof has been verified by our billing team. "
                "Your account is now upgraded to <b>VIP Status</b>!\n\n"
                "Welcome to the family. Check out our VIP Lounge and member perks in <b>'Join Our Family'</b>!"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 VIP Hub", callback_data="btn_family")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_id} of approval: {e}")

async def admin_sub_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    sub_id = int(parts[3])
    user_id = int(parts[4])
    
    await db.update_subscription_status(sub_id, "REJECTED", admin_notes="Rejected by Admin")
    
    await query.edit_message_caption(
        caption=(query.message.caption or "") + "\n\n<b>STATUS:</b> ❌ REJECTED by Admin",
        parse_mode="HTML"
    )
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "⚠️ <b>Payment Verification Notice</b>\n\n"
                "Our billing team was unable to verify the transaction details or receipt you submitted.\n"
                "Please verify your Transaction ID / Hash or open a support ticket to chat directly with billing."
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Open Billing Ticket", callback_data="btn_new_ticket")],
                [InlineKeyboardButton("🧾 Resubmit Receipt", callback_data="sub_submit_proof")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_id} of rejection: {e}")

# --- Stats & Broadcast ---

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id) and update.effective_chat.id != config.ADMIN_GROUP_ID:
        return
        
    total_users = (await db.fetch_one("SELECT COUNT(*) as count FROM users"))["count"]
    total_tickets = (await db.fetch_one("SELECT COUNT(*) as count FROM tickets"))["count"]
    open_tickets = (await db.fetch_one("SELECT COUNT(*) as count FROM tickets WHERE status IN ('OPEN', 'IN_PROGRESS')"))["count"]
    total_complaints = (await db.fetch_one("SELECT COUNT(*) as count FROM complaints"))["count"]
    avg_rating_row = await db.fetch_one("SELECT AVG(rating) as avg_r FROM tickets WHERE rating IS NOT NULL")
    avg_rating = round(avg_rating_row["avg_r"], 2) if avg_rating_row and avg_rating_row["avg_r"] else "N/A"
    
    stats_text = (
        f"📊 <b>Support Bot Performance Dashboard</b>\n\n"
        f"👥 <b>Total Registered Users:</b> <code>{total_users}</code>\n"
        f"🎫 <b>Total Tickets Created:</b> <code>{total_tickets}</code>\n"
        f"🟡 <b>Open / Active Tickets:</b> <code>{open_tickets}</code>\n"
        f"🚨 <b>Formal Complaints:</b> <code>{total_complaints}</code>\n"
        f"⭐ <b>Average CSAT Rating:</b> <code>{avg_rating} / 5.0</code>\n"
    )
    
    await update.message.reply_text(stats_text, parse_mode="HTML")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Super Admin permission required.")
        return
        
    if not context.args:
        await update.message.reply_text("Usage: <code>/broadcast Your message text here</code>", parse_mode="HTML")
        return
        
    broadcast_text = " ".join(context.args)
    users = await db.fetch_all("SELECT user_id FROM users WHERE is_banned = 0")
    
    sent_count = 0
    fail_count = 0
    
    status_msg = await update.message.reply_text(f"🚀 Broadcasting to {len(users)} users...")
    
    for u in users:
        try:
            await context.bot.send_message(
                chat_id=u["user_id"],
                text=f"📢 <b>Important Announcement:</b>\n\n{escape_html(broadcast_text)}",
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception:
            fail_count += 1
            
    await status_msg.edit_text(
        f"✅ <b>Broadcast Completed!</b>\n\n"
        f"• Delivered: <code>{sent_count}</code>\n"
        f"• Failed/Blocked: <code>{fail_count}</code>",
        parse_mode="HTML"
    )
