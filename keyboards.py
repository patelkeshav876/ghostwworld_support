from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from config import config

def get_main_menu_keyboard(has_active_ticket: bool = False) -> InlineKeyboardMarkup:
    keyboard = []
    
    if has_active_ticket:
        keyboard.append([
            InlineKeyboardButton("💬 Current Active Ticket (Chat Live)", callback_data="btn_active_ticket")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("💬 Ask Question / Open Ticket", callback_data="btn_new_ticket")
        ])
        
    keyboard.append([
        InlineKeyboardButton("💳 Subscription & Billing", callback_data="btn_subscriptions"),
        InlineKeyboardButton("🚨 File a Complaint", callback_data="btn_complaint")
    ])
    
    keyboard.append([
        InlineKeyboardButton("❓ Instant FAQ & Guides", callback_data="btn_faq"),
        InlineKeyboardButton("🤝 Join Our Family", callback_data="btn_family")
    ])
    
    webapp_row = []
    if config.WEBAPP_URL and config.WEBAPP_URL.startswith("https://"):
        try:
            webapp_row.append(
                InlineKeyboardButton("🌐 Open WebApp", web_app=WebAppInfo(url=config.WEBAPP_URL))
            )
        except Exception:
            webapp_row.append(
                InlineKeyboardButton("🌐 Visit WebApp", url=config.WEBAPP_URL)
            )
            
    webapp_row.append(InlineKeyboardButton("📋 My Tickets", callback_data="btn_my_tickets"))
    keyboard.append(webapp_row)
    
    return InlineKeyboardMarkup(keyboard)

def get_products_keyboard(action_prefix: str) -> InlineKeyboardMarkup:
    """Returns dynamic products buttons based on config.ECOSYSTEM_PRODUCTS"""
    keyboard = []
    for code, info in config.ECOSYSTEM_PRODUCTS.items():
        keyboard.append([
            InlineKeyboardButton(info["name"], callback_data=f"{action_prefix}_{code}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard(callback_data: str = "btn_cancel_wizard") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel & Return", callback_data=callback_data)]
    ])

def get_csat_keyboard(ticket_id: str) -> InlineKeyboardMarkup:
    """Customer Satisfaction (CSAT) rating buttons"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐ 1", callback_data=f"rate_{ticket_id}_1"),
            InlineKeyboardButton("⭐ 2", callback_data=f"rate_{ticket_id}_2"),
            InlineKeyboardButton("⭐ 3", callback_data=f"rate_{ticket_id}_3"),
            InlineKeyboardButton("⭐ 4", callback_data=f"rate_{ticket_id}_4"),
            InlineKeyboardButton("⭐ 5", callback_data=f"rate_{ticket_id}_5"),
        ],
        [InlineKeyboardButton("💬 Leave Feedback Note", callback_data=f"feedback_{ticket_id}")]
    ])

def get_admin_ticket_keyboard(ticket_id: str, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Mark as Resolved", callback_data=f"adm_resolve_{ticket_id}"),
            InlineKeyboardButton("🚨 Set High Priority", callback_data=f"adm_prio_{ticket_id}")
        ],
        [
            InlineKeyboardButton("👤 User Info", callback_data=f"adm_uinfo_{user_id}"),
            InlineKeyboardButton("🚫 Ban User", callback_data=f"adm_ban_{user_id}")
        ]
    ])

def get_family_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📢 Official Channel", url=config.OFFICIAL_CHANNEL_URL),
            InlineKeyboardButton("💬 Community Group", url=config.COMMUNITY_CHAT_URL)
        ],
        [
            InlineKeyboardButton("💎 VIP Member Lounge", url=config.VIP_CHAT_URL),
            InlineKeyboardButton("🌐 Official Website", url=config.WEBSITE_URL)
        ],
        [
            InlineKeyboardButton("🎁 Refer & Earn Rewards", callback_data="btn_referral_info")
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_subscription_options_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧾 Submit Payment Receipt / TxID", callback_data="sub_submit_proof")
        ],
        [
            InlineKeyboardButton("💳 Subscription Plans & Pricing", callback_data="sub_plans_info"),
            InlineKeyboardButton("🔄 Refund / Billing Issue", callback_data="sub_refund_issue")
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="btn_main_menu")
        ]
    ])

def get_admin_subscription_review_keyboard(sub_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve & Grant VIP", callback_data=f"adm_sub_approve_{sub_id}_{user_id}"),
            InlineKeyboardButton("❌ Reject Proof", callback_data=f"adm_sub_reject_{sub_id}_{user_id}")
        ]
    ])
