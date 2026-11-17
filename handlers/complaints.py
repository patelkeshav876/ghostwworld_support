import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from keyboards import get_products_keyboard, get_cancel_keyboard
from utils.helpers import escape_html, format_user_mention, generate_ticket_id, safe_edit_message
from utils.telegram_features import create_ticket_topic
from config import config

logger = logging.getLogger(__name__)

COMPLAINT_SELECT_PRODUCT, COMPLAINT_ENTER_TEXT, COMPLAINT_ENTER_RESOLUTION = range(3)

async def start_complaint_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "🚨 <b>Formal Complaints & Escalation Portal</b>\n\n"
        "We are truly sorry that you experienced an issue. Your feedback is taken with the highest priority "
        "and is sent directly to management.\n\n"
        "<b>Step 1/3:</b> Which service or bot is this complaint regarding?"
    )
    
    await safe_edit_message(
        query=query,
        text=text,
        reply_markup=get_products_keyboard("compprod"),
        parse_mode="HTML"
    )
    return COMPLAINT_SELECT_PRODUCT

async def complaint_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    product_code = query.data.replace("compprod_", "")
    product_info = config.ECOSYSTEM_PRODUCTS.get(product_code, {"name": product_code})
    context.user_data["comp_product"] = product_info["name"]
    
    text = (
        f"📦 <b>Selected:</b> {product_info['name']}\n\n"
        f"<b>Step 2/3:</b> Please describe what happened in detail.\n"
        f"<i>Include any dates, error messages, or context that helps us investigate.</i>\n\n"
        f"Type your complaint below:"
    )
    
    await safe_edit_message(
        query=query,
        text=text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    return COMPLAINT_ENTER_TEXT

async def complaint_text_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    complaint_body = update.message.text.strip()
    context.user_data["comp_text"] = complaint_body
    
    text = (
        f"📝 <b>Complaint Recorded</b>\n\n"
        f"<b>Step 3/3:</b> What outcome or resolution are you seeking?\n"
        f"<i>(e.g., 'Full refund', 'Fix feature bug', 'Account compensation', 'Technical explanation')</i>\n\n"
        f"Type your expected resolution:"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    return COMPLAINT_ENTER_RESOLUTION

async def complaint_resolution_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    resolution_demanded = update.message.text.strip()
    product = context.user_data.get("comp_product", "General")
    complaint_body = context.user_data.get("comp_text", "")
    
    ticket_id = generate_ticket_id(prefix="CMP")
    
    # Create ticket in DB with HIGH priority
    await db.create_ticket(
        ticket_id=ticket_id,
        user_id=user.id,
        product=product,
        category="COMPLAINT",
        description=f"{complaint_body}\n\n[Desired Resolution]: {resolution_demanded}",
        priority="HIGH"
    )
    
    # Create dedicated complaint record
    await db.add_complaint(
        ticket_id=ticket_id,
        user_id=user.id,
        product=product,
        complaint_text=complaint_body,
        desired_resolution=resolution_demanded
    )
    
    # Notify user
    await update.message.reply_text(
        f"🚨 <b>Complaint Registered & Escalated</b>\n\n"
        f"<b>Complaint ID:</b> <code>{ticket_id}</code>\n"
        f"<b>Priority:</b> 🔴 HIGH / URGENT\n"
        f"<b>Product:</b> {escape_html(product)}\n\n"
        f"Your grievance has been forwarded directly to our senior administrative team. "
        f"You will receive a response right here in this chat shortly.\n\n"
        f"<i>You can send further messages, logs, or screenshots anytime now.</i>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="btn_main_menu")]
        ]),
        parse_mode="HTML"
    )
    
    # Create Forum Topic in Admin Supergroup
    if config.ADMIN_GROUP_ID != 0:
        topic_name = f"🚨 {ticket_id} - {user.first_name}"
        thread_id = None
        if config.USE_FORUM_TOPICS:
            thread_id = await create_ticket_topic(
                bot=context.bot,
                chat_id=config.ADMIN_GROUP_ID,
                title=topic_name,
                icon_color=0xFB6F59 # Red/Coral for urgent complaints
            )
            if thread_id:
                await db.set_ticket_forum_topic(ticket_id, thread_id)
                
        admin_alert = (
            f"🚨 <b>URGENT COMPLAINT ESCALATION</b> <code>[{ticket_id}]</code>\n\n"
            f"👤 <b>Complainant:</b> {format_user_mention(user.id, user.first_name, user.username)}\n"
            f"📦 <b>Product:</b> {escape_html(product)}\n\n"
            f"📝 <b>Complaint Details:</b>\n<i>{escape_html(complaint_body)}</i>\n\n"
            f"🎯 <b>Desired Resolution:</b>\n<b>{escape_html(resolution_demanded)}</b>\n\n"
            f"⚡ <i>Staff: Reply to this message or in this topic to communicate with the user.</i>"
        )
        
        try:
            await context.bot.send_message(
                chat_id=config.ADMIN_GROUP_ID,
                message_thread_id=thread_id,
                text=admin_alert,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to post complaint to admin group: {e}")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_complaint_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Cancelled.")
    context.user_data.clear()
    
    await safe_edit_message(
        query=query,
        text="❌ Complaint filing cancelled.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="btn_main_menu")]
        ])
    )
    return ConversationHandler.END
