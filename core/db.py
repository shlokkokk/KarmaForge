"""
KarmaForge SQLite Database Layer
Handles state persistence with WAL mode and robust concurrency guards.
"""

import sqlite3
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any

DB_PATH = Path(os.environ.get("KARMAFORGE_DB_PATH", Path(__file__).resolve().parent.parent / "karmaforge.db"))

def get_connection() -> sqlite3.Connection:
    """Return a thread-safe SQLite connection configured for concurrent safety."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    """Initialize database tables and indexes."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS targeted_posts (
                post_id TEXT PRIMARY KEY,
                subreddit TEXT NOT NULL,
                title TEXT,
                account_username TEXT NOT NULL,
                targeted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS comments_posted (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id TEXT UNIQUE NOT NULL,
                post_id TEXT NOT NULL,
                account_username TEXT NOT NULL,
                subreddit TEXT NOT NULL,
                post_title TEXT,
                post_url TEXT,
                comment_text TEXT NOT NULL,
                persona_used TEXT,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                score INTEGER DEFAULT 1,
                peak_score INTEGER DEFAULT 1,
                score_history TEXT DEFAULT '[]',
                replies_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'HEALTHY',
                deleted INTEGER DEFAULT 0,
                last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS karma_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_username TEXT NOT NULL,
                comment_karma INTEGER NOT NULL,
                post_karma INTEGER NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS daily_quota (
                date_str TEXT NOT NULL,
                account_username TEXT NOT NULL,
                comments_count INTEGER DEFAULT 0,
                PRIMARY KEY (date_str, account_username)
            );

            CREATE INDEX IF NOT EXISTS idx_comments_check 
            ON comments_posted (deleted, posted_at);
        """)

        # Backward compatibility migration for older DBs
        cursor = conn.execute("PRAGMA table_info(comments_posted);")
        columns = [row["name"] for row in cursor.fetchall()]
        if "peak_score" not in columns:
            conn.execute("ALTER TABLE comments_posted ADD COLUMN peak_score INTEGER DEFAULT 1;")
        if "score_history" not in columns:
            conn.execute("ALTER TABLE comments_posted ADD COLUMN score_history TEXT DEFAULT '[]';")
        if "replies_count" not in columns:
            conn.execute("ALTER TABLE comments_posted ADD COLUMN replies_count INTEGER DEFAULT 0;")
        if "status" not in columns:
            conn.execute("ALTER TABLE comments_posted ADD COLUMN status TEXT DEFAULT 'HEALTHY';")

def has_post_been_targeted(post_id: str) -> bool:
    """Check if ANY account has already targeted or commented on this post."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM targeted_posts WHERE post_id = ?", (post_id,)
        ).fetchone()
        return row is not None

def record_comment(
    comment_id: str,
    post_id: str,
    account_username: str,
    subreddit: str,
    post_title: str,
    post_url: str,
    comment_text: str,
    persona_used: str
):
    """Atomically record a posted comment and reserve the post globally."""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        # Mark post as targeted so no other account touches it
        conn.execute(
            """INSERT OR REPLACE INTO targeted_posts (post_id, subreddit, title, account_username)
               VALUES (?, ?, ?, ?)""",
            (post_id, subreddit, post_title, account_username)
        )
        # Record comment entry
        conn.execute(
            """INSERT INTO comments_posted (
                comment_id, post_id, account_username, subreddit, post_title, post_url, comment_text, persona_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (comment_id, post_id, account_username, subreddit, post_title, post_url, comment_text, persona_used)
        )
        # Increment daily quota counter
        conn.execute(
            """INSERT INTO daily_quota (date_str, account_username, comments_count)
               VALUES (?, ?, 1)
               ON CONFLICT(date_str, account_username) 
               DO UPDATE SET comments_count = comments_count + 1""",
            (today, account_username)
        )

def get_daily_comment_count(account_username: str) -> int:
    """Get the number of comments posted today by this account."""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT comments_count FROM daily_quota WHERE date_str = ? AND account_username = ?",
            (today, account_username)
        ).fetchone()
        return row["comments_count"] if row else 0

def get_active_comments(window_hours: int = 36) -> List[Dict[str, Any]]:
    """Retrieve non-deleted comments posted within the tracking window."""
    threshold_time = (datetime.now() - timedelta(hours=window_hours)).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM comments_posted 
               WHERE deleted = 0 AND posted_at >= ?
               ORDER BY posted_at DESC""",
            (threshold_time,)
        ).fetchall()
        return [dict(r) for r in rows]

def update_comment_score(
    comment_id: str,
    score: int,
    deleted: bool = False,
    peak_score: Optional[int] = None,
    score_history: Optional[str] = None,
    replies_count: Optional[int] = None,
    status: Optional[str] = None
):
    """Update live score, peak score, trajectory, and deletion state for a monitored comment."""
    with get_connection() as conn:
        updates = ["score = ?", "deleted = ?", "last_checked_at = CURRENT_TIMESTAMP"]
        params: List[Any] = [score, 1 if deleted else 0]

        if peak_score is not None:
            updates.append("peak_score = MAX(COALESCE(peak_score, 1), ?)")
            params.append(peak_score)
        if score_history is not None:
            updates.append("score_history = ?")
            params.append(score_history)
        if replies_count is not None:
            updates.append("replies_count = ?")
            params.append(replies_count)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        params.append(comment_id)
        sql = f"UPDATE comments_posted SET {', '.join(updates)} WHERE comment_id = ?"
        conn.execute(sql, tuple(params))

def get_recent_comments(account_username: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch recent comments for CLI status or Discord commands."""
    with get_connection() as conn:
        if account_username:
            rows = conn.execute(
                """SELECT * FROM comments_posted 
                   WHERE account_username = ? 
                   ORDER BY posted_at DESC LIMIT ?""",
                (account_username, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM comments_posted 
                   ORDER BY posted_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

def record_karma(account_username: str, comment_karma: int, post_karma: int):
    """Log current karma snapshot for velocity calculations."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO karma_history (account_username, comment_karma, post_karma)
               VALUES (?, ?, ?)""",
            (account_username, comment_karma, post_karma)
        )

def get_latest_karma(account_username: str) -> Optional[Dict[str, int]]:
    """Fetch the most recent karma snapshot for an account."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT comment_karma, post_karma FROM karma_history 
               WHERE account_username = ? 
               ORDER BY recorded_at DESC LIMIT 1""",
            (account_username,)
        ).fetchone()
        if row:
            return {"comment_karma": row["comment_karma"], "post_karma": row["post_karma"]}
        return None

# Initialize on import
init_db()
