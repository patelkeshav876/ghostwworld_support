import os
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Config:
    # Telegram Bot Token from @BotFather
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    # ID of the Private Staff/Admin Supergroup where tickets are managed.
    # Note: Enable "Topics" in this group to use modern Telegram Forum Tickets!
    ADMIN_GROUP_ID: int = int(os.getenv("ADMIN_GROUP_ID", "0"))
    
    # List of individual Super Admin Telegram User IDs
    SUPER_ADMINS: List[int] = tuple(int(x.strip()) for x in os.getenv("SUPER_ADMINS", "").split(",") if x.strip())
    
    # Use Telegram Forum Topics (True = one topic per ticket in Admin Group, False = standard reply relay)
    USE_FORUM_TOPICS: bool = os.getenv("USE_FORUM_TOPICS", "True").lower() in ("true", "1", "yes")
    
    # WebApp URL for your main website/app
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "https://yourwebapp.example.com")
    
    # Community & "Join Our Family" Links
    OFFICIAL_CHANNEL_URL: str = os.getenv("OFFICIAL_CHANNEL_URL", "https://t.me/your_channel")
    COMMUNITY_CHAT_URL: str = os.getenv("COMMUNITY_CHAT_URL", "https://t.me/your_community")
    VIP_CHAT_URL: str = os.getenv("VIP_CHAT_URL", "https://t.me/your_vip_lounge")
    WEBSITE_URL: str = os.getenv("WEBSITE_URL", "https://yourwebapp.example.com")
    
    # Supported Ecosystem Products
    ECOSYSTEM_PRODUCTS = {
        "webapp": {"name": "🌐 Web Application", "code": "webapp"},
        "bot_trading": {"name": "📈 Trading / Signals Bot", "code": "bot_trading"},
        "bot_ai": {"name": "🧠 AI Assistant Bot", "code": "bot_ai"},
        "bot_store": {"name": "🛍️ Digital Store Bot", "code": "bot_store"},
        "other": {"name": "⚡ General Ecosystem", "code": "other"}
    }
    
    # Startup Banner Image
    STARTUP_IMAGE_PATH: str = os.getenv("STARTUP_IMAGE_PATH", "assets/startup.jpg")

    # Database path
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "ghost_support.db")

config = Config()
