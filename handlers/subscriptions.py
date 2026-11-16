import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from keyboards import (
    get_subscription_options_keyboard,
    get_products_keyboard,
    get_cancel_keyboard,
    get_admin_subscription_review_keyboard
)
from utils.helpers import escape_html, format_user_mention
from config import config

logger = logging.getLogger(__name__)

# FSM States
SUB_SELECT_PRODUCT, SUB_ENTER_PLAN, SUB_SUBMIT_PROOF = range(3)

async def subscription_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db_user = await db.fetch_one("SELECT * FROM users WHERE user_id = ?", (user.id,))
    is_vip = bool(db_user and db_user.get("is_vip"))
    
    status_badge = "👑 <b>Active VIP Subscription</b>" if is_vip else "⚪ <b>No Active Paid Plan</b>"
    
    text = (
        f"💳 <b>Subscription & Billing Center</b>\n"
        f"Account Status: {status_badge}\n\n"
        f"Manage your payments, verify recent transactions, or explore upgrades for our webapp and bots.\n\n"
        f"• <b>Submit Payment Receipt / TxID:</b> Upload transaction proof for rapid activation.\n"
        f"• <b>Plans & Pricing:</b> Review tiers and accepted payment methods (Crypto, Card, Stripe).\n"
        f"• <b>Refund / Billing Inquiry:</b> Open a high-priority ticket with our billing department."
    )
    
    await query.edit_message_text(
        text,
        reply_markup=get_subscription_options_keyboard(),
        parse_mode="HTML"
    )

async def plans_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "💎 <b>Our Subscription Tiers</b>\n\n"
        "<b>1. Web App Pro:</b> $19/month\n"
        "• Unlimited API access\n"
        "• Real-time analytics & custom dashboard\n"
        "• Priority customer support\n\n"
        "<b>2. Multi-Bot All-Access Pass:</b> $29/month\n"
        "• Access to Trading, AI, and Store Bots\n"
        "• VIP Community Lounge membership\n"
        "• Zero-delay notifications & custom signals\n\n"
        "<b>3. Enterprise / Lifetime Bundle:</b> $199\n"
        "• Permanent access to all current and future bots + webapp\n"
        "• Dedicated 1-on-1 account manager\n\n"
        "💳 <b>Accepted Payment Methods:</b> USDT (TRC20/BEP20), BTC, ETH, Solana, Stripe / Credit Card.\n\n"
        "<i>To activate a manual or crypto payment, tap 'Submit Receipt / TxID' below!</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🧾 Submit Payment Proof", callback_data="sub_submit_proof")],
        [InlineKeyboardButton("🔙 Back to Billing", callback_data="btn_subscriptions")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --- Proof Submission Wizard ---

async def start_proof_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "🧾 <b>Payment Verification Wizard (Step 1/3)</b>\n\n"
        "Which product or service did you purchase?"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=get_products_keyboard("subprod"),
        parse_mode="HTML"
    )
    return SUB_SELECT_PRODUCT

async def proof_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    product_code = query.data.replace("subprod_", "")
    product_info = config.ECOSYSTEM_PRODUCTS.get(product_code, {"name": product_code})
    context.user_data["sub_product"] = product_info["name"]
    
    text = (
        f"📦 <b>Selected Product:</b> {product_info['name']}\n\n"
        f"<b>Step 2/3:</b> What plan did you pay for?\n"
        f"<i>(e.g., '1 Month Pro', 'Yearly Pass', 'Lifetime VIP')</i>\n\n"
        f"Type and send the plan name:"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    return SUB_ENTER_PLAN

async def proof_plan_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_name = update.message.text.strip()
    context.user_data["sub_plan"] = plan_name
    
    text = (
        f"✅ <b>Plan:</b> {escape_html(plan_name)}\n\n"
        f"<b>Step 3/3:</b> Please provide your proof of payment.\n\n"
        f"You can send:\n"
        f"• The <b>Transaction ID / Hash</b> (as text)\n"
        f"• OR upload a <b>screenshot / receipt image</b> directly into this chat.\n\n"
        f"Send your proof now:"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    return SUB_SUBMIT_PROOF

async def proof_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    product = context.user_data.get("sub_product", "General")
    plan = context.user_data.get("sub_plan", "Standard")
    
    tx_id = None
    receipt_file_id = None
    
    if update.message.photo:
        receipt_file_id = update.message.photo[-1].file_id
        tx_id = update.message.caption or "Image receipt provided"
    elif update.message.document:
        receipt_file_id = update.message.document.file_id
        tx_id = update.message.caption or "Document receipt provided"
    elif update.message.text:
        tx_id = update.message.text.strip()
    else:
        await update.message.reply_text("Please send text or an image receipt.")
        return SUB_SUBMIT_PROOF

    sub_id = await db.add_subscription_proof(
        user_id=user.id,
        product=product,
        plan_name=plan,
        tx_id=tx_id,
        receipt_file_id=receipt_file_id
    )

    # Notify user
    await update.message.reply_text(
        f"🎉 <b>Receipt Submitted Successfully!</b>\n\n"
        f"<b>Reference #:</b> <code>SUB-{sub_id}</code>\n"
        f"<b>Product:</b> {escape_html(product)}\n"
        f"<b>Plan:</b> {escape_html(plan)}\n\n"
        f"Our billing team has been notified. Your subscription will be activated shortly after verification.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="btn_main_menu")]
        ]),
        parse_mode="HTML"
    )

    # Forward to Admin/Staff Supergroup
    if config.ADMIN_GROUP_ID != 0:
        admin_text = (
            f"💳 <b>NEW PAYMENT PROOF RECEIVED</b> <code>[SUB-{sub_id}]</code>\n\n"
            f"👤 <b>User:</b> {format_user_mention(user.id, user.first_name, user.username)}\n"
            f"📦 <b>Product:</b> {escape_html(product)}\n"
            f"💎 <b>Plan:</b> {escape_html(plan)}\n"
            f"📝 <b>Details / TxID:</b> <code>{escape_html(tx_id)}</code>"
        )
        markup = get_admin_subscription_review_keyboard(sub_id, user.id)
        
        try:
            if receipt_file_id:
                await context.bot.send_photo(
                    chat_id=config.ADMIN_GROUP_ID,
                    photo=receipt_file_id,
                    caption=admin_text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=config.ADMIN_GROUP_ID,
                    text=admin_text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Failed to forward payment proof to admin group: {e}")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_proof_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Cancelled.")
    context.user_data.clear()
    
    await query.edit_message_text(
        "❌ Payment submission cancelled.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Back to Main Menu", callback_data="btn_main_menu")]
        ])
    )
    return ConversationHandler.END
