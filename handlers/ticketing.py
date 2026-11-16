import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from keyboards import (
    get_products_keyboard,
    get_cancel_keyboard,
    get_admin_ticket_keyboard,
    get_csat_keyboard
)
from utils.helpers import escape_html, format_user_mention, generate_ticket_id
from utils.telegram_features import create_ticket_topic, try_set_reaction
from config import config

logger = logging.getLogger(__name__)

TICKET_SELECT_PRODUCT, TICKET_SELECT_CATEGORY, TICKET_ENTER_QUERY = range(3)

CATEGORIES = [
    ("🐞 Bug / Technical Issue", "TECH"),
    ("🔑 Account & Login", "AUTH"),
    ("💡 Feature Request", "FEATURE"),
    ("❓ General Question", "GENERAL")
]

async def start_ticket_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    active_ticket = await db.get_active_ticket_for_user(user.id)
    if active_ticket:
        await query.edit_message_text(
            f"ℹ️ <b>Active Ticket Already Open</b>\n\n"
            f"You currently have ticket <code>{active_ticket['ticket_id']}</code> open.\n"
            f"You can simply type your message or upload files directly in this chat, and our agents will receive it!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
            ]),
            parse_mode="HTML"
        )
        return ConversationHandler.END

    text = (
        "💬 <b>Open a Support Ticket (Step 1/3)</b>\n\n"
        "Which product or bot do you need assistance with?"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=get_products_keyboard("tickprod"),
        parse_mode="HTML"
    )
    return TICKET_SELECT_PRODUCT

async def ticket_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    product_code = query.data.replace("tickprod_", "")
    product_info = config.ECOSYSTEM_PRODUCTS.get(product_code, {"name": product_code})
    context.user_data["ticket_product"] = product_info["name"]
    
    keyboard = []
    for cat_name, cat_code in CATEGORIES:
        keyboard.append([InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_code}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="btn_cancel_wizard")])
    
    text = (
        f"📦 <b>Selected Product:</b> {product_info['name']}\n\n"
        f"<b>Step 2/3:</b> What category best describes your issue?"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return TICKET_SELECT_CATEGORY

async def ticket_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cat_code = query.data.replace("cat_", "")
    context.user_data["ticket_cat"] = cat_code
    
    text = (
        "<b>Step 3/3:</b> Please describe your query or problem in detail.\n\n"
        "You can send text, screenshots, voice notes, or documents. "
        "The more details you provide, the faster our team can resolve it!\n\n"
        "<i>Type or send your message now:</i>"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    return TICKET_ENTER_QUERY

async def ticket_query_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    product = context.user_data.get("ticket_product", "General")
    category = context.user_data.get("ticket_cat", "GENERAL")
    
    # Determine content
    message = update.message
    query_text = message.text or message.caption or "Media attachment sent"
    
    ticket_id = generate_ticket_id(prefix="TK")
    
    # Save ticket in database
    await db.create_ticket(
        ticket_id=ticket_id,
        user_id=user.id,
        product=product,
        category=category,
        description=query_text,
        priority="NORMAL"
    )
    
    # Save message in history
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

    await db.add_ticket_message(
        ticket_id=ticket_id,
        sender_type="USER",
        sender_id=user.id,
        text=query_text,
        media_type=media_type,
        media_file_id=media_file_id
    )

    # Reaction feedback
    await try_set_reaction(context.bot, message.chat.id, message.message_id, "👍")

    # Inform user
    await message.reply_text(
        f"✅ <b>Ticket Created Successfully!</b>\n\n"
        f"<b>Ticket ID:</b> <code>{ticket_id}</code>\n"
        f"<b>Product:</b> {escape_html(product)}\n"
        f"<b>Category:</b> {escape_html(category)}\n"
        f"<b>Status:</b> 🟡 In Queue (Waiting for Agent)\n\n"
        f"Our support agents have received your request. "
        f"Any new messages, photos, or documents you send here will be relayed directly to the team working on your ticket.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
        ]),
        parse_mode="HTML"
    )

    # Relay to Admin Group / Forum Topic
    if config.ADMIN_GROUP_ID != 0:
        thread_id = None
        if config.USE_FORUM_TOPICS:
            topic_title = f"💬 {ticket_id} - {user.first_name}"
            thread_id = await create_ticket_topic(
                bot=context.bot,
                chat_id=config.ADMIN_GROUP_ID,
                title=topic_title,
                icon_color=0x6CD97E # Green
            )
            if thread_id:
                await db.set_ticket_forum_topic(ticket_id, thread_id)

        admin_summary = (
            f"🎫 <b>NEW SUPPORT TICKET</b> <code>[{ticket_id}]</code>\n\n"
            f"👤 <b>User:</b> {format_user_mention(user.id, user.first_name, user.username)} (ID: <code>{user.id}</code>)\n"
            f"📦 <b>Product:</b> {escape_html(product)}\n"
            f"🏷️ <b>Category:</b> {escape_html(category)}\n\n"
            f"📝 <b>Initial Query:</b>\n{escape_html(query_text)}\n\n"
            f"💬 <i>Staff can reply directly in this topic/message to chat with the user.</i>"
        )
        
        reply_markup = get_admin_ticket_keyboard(ticket_id, user.id)
        
        try:
            if media_type == "photo" and media_file_id:
                await context.bot.send_photo(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=thread_id,
                    photo=media_file_id,
                    caption=admin_summary,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
            elif media_type == "document" and media_file_id:
                await context.bot.send_document(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=thread_id,
                    document=media_file_id,
                    caption=admin_summary,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
            elif media_type == "voice" and media_file_id:
                await context.bot.send_voice(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=thread_id,
                    voice=media_file_id,
                    caption=admin_summary,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=thread_id,
                    text=admin_summary,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Failed to relay new ticket to admin group: {e}")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_ticket_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Cancelled.")
    context.user_data.clear()
    
    await query.edit_message_text(
        "❌ Ticket creation cancelled.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="btn_main_menu")]
        ])
    )
    return ConversationHandler.END

# --- Relay Live User Messages to Active Ticket ---

async def handle_user_relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Catches all regular messages from private chats when user is NOT in a ConversationHandler.
    If they have an active ticket, forwards the message into the Admin Topic / Supergroup!
    """
    message = update.message
    if not message or update.effective_chat.type != "private":
        return

    user = update.effective_user
    active_ticket = await db.get_active_ticket_for_user(user.id)
    
    if not active_ticket:
        # Prompt user to open a ticket or select an action
        await message.reply_text(
            "👋 You don't have an active ticket open right now.\n"
            "Please use the menu below to open a ticket, check FAQs, or manage your subscriptions.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Open a Ticket", callback_data="btn_new_ticket")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
            ])
        )
        return

    ticket_id = active_ticket["ticket_id"]
    topic_id = active_ticket.get("forum_topic_id")
    
    # Save message in DB
    query_text = message.text or message.caption
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

    await db.add_ticket_message(
        ticket_id=ticket_id,
        sender_type="USER",
        sender_id=user.id,
        text=query_text,
        media_type=media_type,
        media_file_id=media_file_id
    )

    # Soft reaction feedback to user
    await try_set_reaction(context.bot, message.chat.id, message.message_id, "👀")

    # Forward to Admin Group / Topic
    if config.ADMIN_GROUP_ID != 0:
        sender_header = f"👤 <b>{escape_html(user.first_name)}</b> <code>[{ticket_id}]</code>:\n"
        try:
            if media_type == "photo":
                await context.bot.send_photo(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=topic_id,
                    photo=media_file_id,
                    caption=sender_header + (escape_html(query_text) if query_text else ""),
                    parse_mode="HTML"
                )
            elif media_type == "document":
                await context.bot.send_document(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=topic_id,
                    document=media_file_id,
                    caption=sender_header + (escape_html(query_text) if query_text else ""),
                    parse_mode="HTML"
                )
            elif media_type == "voice":
                await context.bot.send_voice(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=topic_id,
                    voice=media_file_id,
                    caption=sender_header,
                    parse_mode="HTML"
                )
            elif media_type == "video":
                await context.bot.send_video(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=topic_id,
                    video=media_file_id,
                    caption=sender_header + (escape_html(query_text) if query_text else ""),
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=config.ADMIN_GROUP_ID,
                    message_thread_id=topic_id,
                    text=f"{sender_header}{escape_html(query_text)}",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Error relaying user message to admin group: {e}")

# --- Ticket List & CSAT Rating ---

async def my_tickets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    tickets = await db.get_user_tickets(user.id, limit=5)
    
    if not tickets:
        await query.edit_message_text(
            "📋 <b>Your Support Tickets</b>\n\nYou haven't submitted any tickets yet.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Open a Ticket", callback_data="btn_new_ticket")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
            ]),
            parse_mode="HTML"
        )
        return

    text = "📋 <b>Your Recent Support Tickets:</b>\n\n"
    for t in tickets:
        status_icon = "🟢" if t["status"] == "RESOLVED" else ("🟡" if t["status"] == "OPEN" else "🔵")
        text += (
            f"{status_icon} <b>#{t['ticket_id']}</b> - <b>{t['product']}</b>\n"
            f"Status: <code>{t['status']}</code> | Created: {t['created_at'][:10]}\n"
            f"<i>{escape_html(t['description'][:60])}...</i>\n\n"
        )
        
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
        ]),
        parse_mode="HTML"
    )

async def csat_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    ticket_id = parts[1]
    stars = int(parts[2])
    
    await db.rate_ticket(ticket_id, stars)
    
    thanks_text = (
        f"🌟 <b>Thank You for Your Feedback!</b>\n\n"
        f"You rated Ticket <code>{ticket_id}</code> with <b>{stars}/5 Stars</b>.\n"
        f"Your feedback helps us continuously improve our support experience."
    )
    
    await query.edit_message_text(
        thanks_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
        ]),
        parse_mode="HTML"
    )
