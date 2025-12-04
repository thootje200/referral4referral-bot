"""
Database module for Referral4Referral Telegram Bot
Handles all SQLite database operations for user data and queue state persistence
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum


class UserStatus(Enum):
    """User status enumeration"""
    WAITING = "waiting"
    ASSIGNED = "assigned"
    DONE = "done"


@dataclass
class User:
    """User data model"""
    user_id: int
    referral_link: str
    status: str  # "waiting", "assigned", "done"
    assigned_to: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_referrals: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class Database:
    """
    SQLite database manager for the referral bot
    Handles user storage, queue persistence, and state management
    """

    def __init__(self, db_path: str = "referral_bot.db"):
        """Initialize database connection and create tables if needed"""
        self.db_path = db_path
        self.init_db()

    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                referral_link TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'waiting',
                assigned_to INTEGER,
                completed_referrals INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create referral history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referral_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referee_id INTEGER NOT NULL,
                completed_at TEXT NOT NULL,
                FOREIGN KEY (referrer_id) REFERENCES users(user_id),
                FOREIGN KEY (referee_id) REFERENCES users(user_id)
            )
        """)

        # Create queue state table (for persistence across restarts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queue_state (
                queue_order TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)

        # Create persistent queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                user_id INTEGER PRIMARY KEY,
                referral_link TEXT NOT NULL,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def add_user(self, user_id: int, referral_link: str) -> bool:
        """
        Add a new user to the database
        Returns True if successful, False if user already exists
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO users (user_id, referral_link, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, referral_link, UserStatus.WAITING.value, now, now))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # User or link already exists
            return False
        finally:
            conn.close()

    def get_user(self, user_id: int) -> Optional[User]:
        """Retrieve a user by user_id"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return User(
                user_id=row["user_id"],
                referral_link=row["referral_link"],
                status=row["status"],
                assigned_to=row["assigned_to"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                completed_referrals=row["completed_referrals"],
            )
        return None

    def user_exists(self, user_id: int) -> bool:
        """Check if a user exists"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def link_exists(self, referral_link: str) -> bool:
        """Check if a referral link is already in the system"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE referral_link = ?", (referral_link,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def update_user_status(self, user_id: int, status: str, assigned_to: Optional[int] = None) -> bool:
        """Update user status"""
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE users
            SET status = ?, assigned_to = ?, updated_at = ?
            WHERE user_id = ?
        """, (status, assigned_to, now, user_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def increment_completed_referrals(self, user_id: int) -> bool:
        """Increment completed referrals count for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE users
            SET completed_referrals = completed_referrals + 1, updated_at = ?
            WHERE user_id = ?
        """, (now, user_id))

        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def remove_user(self, user_id: int) -> bool:
        """Remove a user from the system"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def get_all_users(self) -> List[User]:
        """Get all users"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users ORDER BY created_at ASC")
        rows = cursor.fetchall()
        conn.close()

        return [
            User(
                user_id=row["user_id"],
                referral_link=row["referral_link"],
                status=row["status"],
                assigned_to=row["assigned_to"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                completed_referrals=row["completed_referrals"],
            )
            for row in rows
        ]

    def get_users_by_status(self, status: str) -> List[User]:
        """Get all users with a specific status"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE status = ? ORDER BY created_at ASC", (status,))
        rows = cursor.fetchall()
        conn.close()

        return [
            User(
                user_id=row["user_id"],
                referral_link=row["referral_link"],
                status=row["status"],
                assigned_to=row["assigned_to"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                completed_referrals=row["completed_referrals"],
            )
            for row in rows
        ]

    def add_referral_history(self, referrer_id: int, referee_id: int) -> bool:
        """Record a completed referral"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO referral_history (referrer_id, referee_id, completed_at)
                VALUES (?, ?, ?)
            """, (referrer_id, referee_id, now))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_queue_state(self) -> Optional[List[int]]:
        """Retrieve saved queue state"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT queue_order FROM queue_state LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            try:
                return json.loads(row["queue_order"])
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def save_queue_state(self, queue_order: List[int]) -> bool:
        """Save queue state for persistence"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            now = datetime.now().isoformat()
            # Clear old state and insert new one
            cursor.execute("DELETE FROM queue_state")
            cursor.execute("""
                INSERT INTO queue_state (queue_order, last_updated)
                VALUES (?, ?)
            """, (json.dumps(queue_order), now))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get bot statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM users WHERE status = ?", (UserStatus.WAITING.value,))
        waiting_users = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM users WHERE status = ?", (UserStatus.ASSIGNED.value,))
        assigned_users = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM referral_history")
        completed_referrals = cursor.fetchone()["count"]

        conn.close()

        return {
            "total_users": total_users,
            "waiting_users": waiting_users,
            "assigned_users": assigned_users,
            "completed_referrals": completed_referrals,
        }

    def clear_all(self):
        """Clear all data (useful for testing/reset)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM referral_history")
        cursor.execute("DELETE FROM queue_state")
        cursor.execute("DELETE FROM users")

        conn.commit()
        conn.close()
    def has_interacted_before(self, user_id: int, target_id: int) -> bool:
        """
        Check if user_id has previously interacted with target_id
        Returns True if they have already been paired, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 1 FROM referral_history 
            WHERE referrer_id = ? AND referee_id = ?
        """, (user_id, target_id))
        result = cursor.fetchone()
        conn.close()

        return result is not None

    def queue_add(self, user_id: int, link: str):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO queue (user_id, referral_link)
                VALUES (?, ?)
            """, (user_id, link))


    def queue_pop_first(self):
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT user_id, referral_link FROM queue
                ORDER BY timestamp ASC
                LIMIT 1
            """).fetchone()

            if not row:
                return None, None

            user_id, link = row

            conn.execute("DELETE FROM queue WHERE user_id = ?", (user_id,))
            return user_id, link


    def queue_get_all(self):
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT user_id, referral_link
                FROM queue
                ORDER BY timestamp ASC
            """).fetchall()
            return rows
