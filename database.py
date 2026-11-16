import sqlite3
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import config

class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
        self._init_db_sync()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db_sync(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_banned INTEGER DEFAULT 0,
                is_vip INTEGER DEFAULT 0,
                created_at TEXT
            )
            """)
            
            # Tickets table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                user_id INTEGER,
                product TEXT,
                category TEXT,
                description TEXT,
                status TEXT DEFAULT 'OPEN',
                priority TEXT DEFAULT 'NORMAL',
                forum_topic_id INTEGER DEFAULT NULL,
                rating INTEGER DEFAULT NULL,
                feedback TEXT DEFAULT NULL,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """)
            
            # Ticket messages (history)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT,
                sender_type TEXT, -- 'USER' or 'ADMIN'
                sender_id INTEGER,
                message_text TEXT,
                media_type TEXT,
                media_file_id TEXT,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id)
            )
            """)
            
            # Subscriptions & Payment verification proofs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product TEXT,
                plan_name TEXT,
                tx_id TEXT,
                receipt_file_id TEXT,
                status TEXT DEFAULT 'PENDING', -- 'PENDING', 'APPROVED', 'REJECTED'
                admin_notes TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            """)
            
            # Complaints table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT,
                user_id INTEGER,
                product TEXT,
                complaint_text TEXT,
                desired_resolution TEXT,
                status TEXT DEFAULT 'ESCALATED',
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id)
            )
            """)
            
            conn.commit()

    async def execute_query(self, query: str, params: tuple = ()) -> None:
        def _exec():
            with self._get_connection() as conn:
                conn.execute(query, params)
                conn.commit()
        await asyncio.to_thread(_exec)

    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        def _fetch():
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, params)
                row = cur.fetchone()
                return dict(row) if row else None
        return await asyncio.to_thread(_fetch)

    async def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        def _fetch():
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(query, params)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
        return await asyncio.to_thread(_fetch)

    # User Methods
    async def get_or_create_user(self, user_id: int, username: Optional[str], first_name: str) -> Dict[str, Any]:
        user = await self.fetch_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
        now = datetime.utcnow().isoformat()
        if not user:
            await self.execute_query(
                "INSERT INTO users (user_id, username, first_name, created_at) VALUES (?, ?, ?, ?)",
                (user_id, username, first_name, now)
            )
            user = await self.fetch_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
        else:
            # Update latest username/name
            await self.execute_query(
                "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
                (username, first_name, user_id)
            )
        return user

    async def set_user_banned(self, user_id: int, is_banned: bool) -> None:
        await self.execute_query("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if is_banned else 0, user_id))

    async def set_user_vip(self, user_id: int, is_vip: bool) -> None:
        await self.execute_query("UPDATE users SET is_vip = ? WHERE user_id = ?", (1 if is_vip else 0, user_id))

    # Ticket Methods
    async def create_ticket(self, ticket_id: str, user_id: int, product: str, category: str, description: str, priority: str = "NORMAL") -> None:
        now = datetime.utcnow().isoformat()
        await self.execute_query(
            """INSERT INTO tickets (ticket_id, user_id, product, category, description, status, priority, created_at, updated_at) 
               VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?)""",
            (ticket_id, user_id, product, category, description, priority, now, now)
        )

    async def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        return await self.fetch_one("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))

    async def get_active_ticket_for_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetch_one(
            "SELECT * FROM tickets WHERE user_id = ? AND status IN ('OPEN', 'IN_PROGRESS') ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )

    async def get_ticket_by_topic_id(self, topic_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetch_one("SELECT * FROM tickets WHERE forum_topic_id = ?", (topic_id,))

    async def update_ticket_status(self, ticket_id: str, status: str) -> None:
        now = datetime.utcnow().isoformat()
        await self.execute_query(
            "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
            (status, now, ticket_id)
        )

    async def set_ticket_forum_topic(self, ticket_id: str, forum_topic_id: int) -> None:
        await self.execute_query(
            "UPDATE tickets SET forum_topic_id = ? WHERE ticket_id = ?",
            (forum_topic_id, ticket_id)
        )

    async def rate_ticket(self, ticket_id: str, rating: int, feedback: Optional[str] = None) -> None:
        await self.execute_query(
            "UPDATE tickets SET rating = ?, feedback = ? WHERE ticket_id = ?",
            (rating, feedback, ticket_id)
        )

    async def get_user_tickets(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        return await self.fetch_all(
            "SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )

    # Message Relay History
    async def add_ticket_message(self, ticket_id: str, sender_type: str, sender_id: int, 
                                 text: Optional[str], media_type: Optional[str] = None, media_file_id: Optional[str] = None) -> None:
        now = datetime.utcnow().isoformat()
        await self.execute_query(
            """INSERT INTO ticket_messages (ticket_id, sender_type, sender_id, message_text, media_type, media_file_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ticket_id, sender_type, sender_id, text, media_type, media_file_id, now)
        )

    # Subscriptions & Proofs
    async def add_subscription_proof(self, user_id: int, product: str, plan_name: str, tx_id: Optional[str], receipt_file_id: Optional[str]) -> int:
        now = datetime.utcnow().isoformat()
        def _insert():
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """INSERT INTO subscriptions (user_id, product, plan_name, tx_id, receipt_file_id, status, created_at)
                       VALUES (?, ?, ?, ?, ?, 'PENDING', ?)""",
                    (user_id, product, plan_name, tx_id, receipt_file_id, now)
                )
                conn.commit()
                return cur.lastrowid
        return await asyncio.to_thread(_insert)

    async def update_subscription_status(self, sub_id: int, status: str, admin_notes: Optional[str] = None) -> None:
        await self.execute_query(
            "UPDATE subscriptions SET status = ?, admin_notes = ? WHERE id = ?",
            (status, admin_notes, sub_id)
        )

    async def get_subscription(self, sub_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetch_one("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))

    # Complaints
    async def add_complaint(self, ticket_id: str, user_id: int, product: str, complaint_text: str, desired_resolution: str) -> None:
        now = datetime.utcnow().isoformat()
        await self.execute_query(
            """INSERT INTO complaints (ticket_id, user_id, product, complaint_text, desired_resolution, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'ESCALATED', ?)""",
            (ticket_id, user_id, product, complaint_text, desired_resolution, now)
        )

db = Database()
