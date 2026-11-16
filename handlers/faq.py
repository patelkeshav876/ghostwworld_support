from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

FAQ_ITEMS = {
    "faq_webapp_login": {
        "title": "🔑 Can't log into the Web App?",
        "answer": (
            "<b>🔑 Web App Login Troubleshooting:</b>\n\n"
            "1. <b>Password Reset:</b> Visit the webapp login page and click <i>'Forgot Password'</i> to receive a reset code.\n"
            "2. <b>Browser Cache:</b> Try clearing your browser cache/cookies or opening the app in an Incognito / Private window.\n"
            "3. <b>Telegram Login:</b> If you use Telegram Login widget, ensure third-party cookies are enabled in your browser settings.\n\n"
            "<i>Still stuck? Open a ticket below to get direct assistance!</i>"
        )
    },
    "faq_sub_activation": {
        "title": "⚡ How long does subscription activation take?",
        "answer": (
            "<b>⚡ Subscription Activation Times:</b>\n\n"
            "• <b>Cards & Stripe:</b> Instant (within 1-2 minutes).\n"
            "• <b>Crypto Payments:</b> Activated automatically after 1-3 network confirmations.\n"
            "• <b>Manual Transfers:</b> If you paid manually, submit your Transaction ID / receipt via the <b>'Subscription & Billing'</b> button in the main menu for fast review!"
        )
    },
    "faq_bot_commands": {
        "title": "🤖 Bot not responding or commands failed?",
        "answer": (
            "<b>🤖 Bot Troubleshooting Checklist:</b>\n\n"
            "1. Send <code>/start</code> in the specific bot to wake up your session.\n"
            "2. Ensure you have not blocked or muted the bot notifications.\n"
            "3. Check our official announcements channel for any scheduled maintenance.\n"
            "4. If a specific command is throwing errors, take a screenshot and submit a ticket here."
        )
    },
    "faq_refund_policy": {
        "title": "🔄 What is our Refund Policy?",
        "answer": (
            "<b>🔄 Refund & Guarantee Policy:</b>\n\n"
            "We offer a 7-day satisfaction warranty on qualifying plans if the service does not perform as advertised.\n"
            "To initiate a refund review, navigate to <b>'Subscription & Billing'</b> ➔ <b>'Refund / Billing Issue'</b>."
        )
    }
}

async def faq_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for key, item in FAQ_ITEMS.items():
        keyboard.append([InlineKeyboardButton(item["title"], callback_data=f"show_{key}")])
    
    keyboard.append([InlineKeyboardButton("💬 Can't find answer? Contact Support", callback_data="btn_new_ticket")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")])
    
    text = (
        "❓ <b>Instant Knowledge Base & Self-Help</b>\n\n"
        "Select a topic below for instant solutions to common issues:"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def faq_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    faq_key = query.data.replace("show_", "")
    item = FAQ_ITEMS.get(faq_key)
    
    if not item:
        await query.edit_message_text("Topic not found.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to FAQ", callback_data="btn_faq")]
        ]))
        return

    keyboard = [
        [InlineKeyboardButton("💬 Still Need Help? Open Ticket", callback_data="btn_new_ticket")],
        [InlineKeyboardButton("🔙 Back to FAQ List", callback_data="btn_faq")]
    ]
    
    await query.edit_message_text(
        item["answer"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
