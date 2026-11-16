import logging
import asyncio
import os
import json
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters
)

from config import config
from handlers.start import start_command, main_menu_callback
from handlers.faq import faq_menu_callback, faq_detail_callback
from handlers.family import family_menu_callback, referral_info_callback
from handlers.subscriptions import (
    subscription_menu_callback,
    plans_info_callback,
    start_proof_submission,
    proof_product_selected,
    proof_plan_entered,
    proof_received,
    cancel_proof_wizard,
    SUB_SELECT_PRODUCT,
    SUB_ENTER_PLAN,
    SUB_SUBMIT_PROOF
)
from handlers.complaints import (
    start_complaint_flow,
    complaint_product_selected,
    complaint_text_entered,
    complaint_resolution_entered,
    cancel_complaint_wizard,
    COMPLAINT_SELECT_PRODUCT,
    COMPLAINT_ENTER_TEXT,
    COMPLAINT_ENTER_RESOLUTION
)
from handlers.ticketing import (
    start_ticket_creation,
    ticket_product_selected,
    ticket_category_selected,
    ticket_query_received,
    cancel_ticket_wizard,
    handle_user_relay_message,
    my_tickets_callback,
    csat_rating_callback,
    TICKET_SELECT_PRODUCT,
    TICKET_SELECT_CATEGORY,
    TICKET_ENTER_QUERY
)
from handlers.admin import (
    handle_admin_group_message,
    close_command,
    stats_command,
    broadcast_command,
    admin_resolve_callback,
    admin_ban_callback,
    admin_sub_approve_callback,
    admin_sub_reject_callback
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_START_TIME = datetime.now(timezone.utc)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def _send_health_response(self, is_head=False):
        uptime_seconds = int((datetime.now(timezone.utc) - BOT_START_TIME).total_seconds())
        response_data = {
            "status": "healthy",
            "service": "ghost_support_bot",
            "uptime_seconds": uptime_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        body = json.dumps(response_data, indent=2).encode("utf-8")
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        if not is_head:
            self.wfile.write(body)

    def do_GET(self):
        # Supports /, /health, /api/health, /ping
        self._send_health_response(is_head=False)

    def do_HEAD(self):
        # UptimeRobot often sends HEAD requests to save bandwidth
        self._send_health_response(is_head=True)

    def log_message(self, format, *args):
        # Silence routine ping logs to keep console clean
        pass

def start_health_server():
    port_env = os.getenv("PORT")
    if port_env:
        try:
            port = int(port_env)
            server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            logger.info(f"🌐 Cloud health & UptimeRobot API listening on port {port} (/health, /api/health).")
        except Exception as e:
            logger.warning(f"Could not bind health check server: {e}")

def main():
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.warning(
            "⚠️ BOT_TOKEN is not set in config or environment! "
            "Please configure your token in .env or config.py before running."
        )

    # Build Application
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # --- 1. Basic Navigation & Hub Handlers ---
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^btn_main_menu$"))
    app.add_handler(CallbackQueryHandler(my_tickets_callback, pattern="^btn_my_tickets$"))
    
    # FAQ Handlers
    app.add_handler(CallbackQueryHandler(faq_menu_callback, pattern="^btn_faq$"))
    app.add_handler(CallbackQueryHandler(faq_detail_callback, pattern="^show_"))
    
    # "Join Our Family" Community Hub
    app.add_handler(CallbackQueryHandler(family_menu_callback, pattern="^btn_family$"))
    app.add_handler(CallbackQueryHandler(referral_info_callback, pattern="^btn_referral_info$"))
    
    # Subscriptions & Billing
    app.add_handler(CallbackQueryHandler(subscription_menu_callback, pattern="^btn_subscriptions$"))
    app.add_handler(CallbackQueryHandler(plans_info_callback, pattern="^sub_plans_info$"))

    # --- 2. Multi-Step Conversation Handlers (FSM) ---

    # Ticket Creation Wizard
    ticket_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_ticket_creation, pattern="^(btn_new_ticket|sub_refund_issue)$")
        ],
        states={
            TICKET_SELECT_PRODUCT: [
                CallbackQueryHandler(ticket_product_selected, pattern="^tickprod_")
            ],
            TICKET_SELECT_CATEGORY: [
                CallbackQueryHandler(ticket_category_selected, pattern="^cat_")
            ],
            TICKET_ENTER_QUERY: [
                MessageHandler(filters.ALL & ~filters.COMMAND, ticket_query_received)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_ticket_wizard, pattern="^btn_cancel_wizard$"),
            CallbackQueryHandler(main_menu_callback, pattern="^btn_main_menu$")
        ],
        allow_reentry=True
    )
    app.add_handler(ticket_conv)

    # Subscription Proof Submission Wizard
    sub_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_proof_submission, pattern="^sub_submit_proof$")
        ],
        states={
            SUB_SELECT_PRODUCT: [
                CallbackQueryHandler(proof_product_selected, pattern="^subprod_")
            ],
            SUB_ENTER_PLAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, proof_plan_entered)
            ],
            SUB_SUBMIT_PROOF: [
                MessageHandler(filters.ALL & ~filters.COMMAND, proof_received)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_proof_wizard, pattern="^btn_cancel_wizard$"),
            CallbackQueryHandler(main_menu_callback, pattern="^btn_main_menu$")
        ],
        allow_reentry=True
    )
    app.add_handler(sub_conv)

    # Complaint & Escalation Wizard
    complaint_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_complaint_flow, pattern="^btn_complaint$")
        ],
        states={
            COMPLAINT_SELECT_PRODUCT: [
                CallbackQueryHandler(complaint_product_selected, pattern="^compprod_")
            ],
            COMPLAINT_ENTER_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_text_entered)
            ],
            COMPLAINT_ENTER_RESOLUTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_resolution_entered)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_complaint_wizard, pattern="^btn_cancel_wizard$"),
            CallbackQueryHandler(main_menu_callback, pattern="^btn_main_menu$")
        ],
        allow_reentry=True
    )
    app.add_handler(complaint_conv)

    # --- 3. CSAT Rating & Feedback ---
    app.add_handler(CallbackQueryHandler(csat_rating_callback, pattern="^rate_"))

    # --- 4. Admin Management Handlers ---
    app.add_handler(CommandHandler("close", close_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    
    app.add_handler(CallbackQueryHandler(admin_resolve_callback, pattern="^adm_resolve_"))
    app.add_handler(CallbackQueryHandler(admin_ban_callback, pattern="^adm_ban_"))
    app.add_handler(CallbackQueryHandler(admin_sub_approve_callback, pattern="^adm_sub_approve_"))
    app.add_handler(CallbackQueryHandler(admin_sub_reject_callback, pattern="^adm_sub_reject_"))

    # --- 5. Message Relays ---
    # Staff Group Relay (Admin -> User)
    if config.ADMIN_GROUP_ID != 0:
        app.add_handler(MessageHandler(
            filters.Chat(config.ADMIN_GROUP_ID) & ~filters.COMMAND,
            handle_admin_group_message
        ))

    # User Live Relay (User -> Admin Group/Topic)
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_user_relay_message
    ))

    # Start health check server if running on cloud platform (Render/Koyeb)
    start_health_server()

    logger.info("🤖 Support Bot is initializing and polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
