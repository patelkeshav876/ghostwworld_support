from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from keyboards import get_family_keyboard
from database import db
from config import config
from utils.helpers import safe_edit_message

async def family_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db_user = await db.fetch_one("SELECT * FROM users WHERE user_id = ?", (user.id,))
    is_vip = bool(db_user and db_user.get("is_vip"))
    
    vip_badge = "👑 <b>VIP Member</b>" if is_vip else "🌱 <b>Standard Member</b>"
    
    text = (
        f"🤝 <b>Welcome to Our Family!</b>\n"
        f"Status: {vip_badge}\n\n"
        f"We are not just a tool; we are a growing community of creators, traders, and builders. "
        f"Here are the exclusive hubs where you can connect with us:\n\n"
        f"📢 <b>Official Announcements:</b> Product updates, new features, and server alerts.\n"
        f"💬 <b>Community Chat:</b> Share tips, network with fellow users, and talk with the team.\n"
        f"💎 <b>VIP Member Lounge:</b> Exclusive access for active subscribers with beta testing access.\n"
        f"🎁 <b>Referral Rewards:</b> Invite friends and get free subscription extensions!\n\n"
        f"Choose an option below to connect with us:"
    )
    
    await safe_edit_message(
        query=query,
        text=text,
        reply_markup=get_family_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

async def referral_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user.id}"
    
    text = (
        f"🎁 <b>Referral & Ambassador Program</b>\n\n"
        f"Share our platform with friends, colleagues, or your audience and earn rewards!\n\n"
        f"🔗 <b>Your Exclusive Referral Link:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"<b>Perks for Referring:</b>\n"
        f"• 1 Friend Subscribes ➔ +7 Days Free VIP added to your account.\n"
        f"• 5 Friends Subscribe ➔ Lifetime 20% discount on all webapp & bot plans.\n"
        f"• 10+ Friends ➔ Official Ambassador Badge & Direct Hotline to Founders.\n\n"
        f"<i>Tap the link above to copy and share it!</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Family Hub", callback_data="btn_family")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="btn_main_menu")]
    ]
    
    await safe_edit_message(
        query=query,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
