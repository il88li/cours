# database.py
import sqlite3
from typing import Dict, List, Optional

DATABASE = 'courses.db'

def get_db():
    class ConnectionContextManager:
        def __enter__(self):
            self.conn = sqlite3.connect(DATABASE)
            self.conn.row_factory = sqlite3.Row
            return self.conn
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.conn.close()
    return ConnectionContextManager()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        # الكورسات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # الفيديوهات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                video_order INTEGER NOT NULL,
                FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
            )
        ''')
        # المستخدمين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_subscribed BOOLEAN DEFAULT 0,
                invites_count INTEGER DEFAULT 0,
                exempt_from_invites BOOLEAN DEFAULT 0,
                blocked BOOLEAN DEFAULT 0,
                referrer_id INTEGER,
                invite_message_shown BOOLEAN DEFAULT 0,
                invite_rewarded BOOLEAN DEFAULT 0
            )
        ''')
        # الإعدادات العامة
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                       ('invite_system_enabled', 'true'))
        # معرض الإنجازات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,          -- 'text', 'photo', 'video'
                content TEXT,                 -- نص أو file_id
                caption TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # المداد (مقالات)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

# --- دوال المستخدمين ---
def add_or_update_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute('''
                UPDATE users
                SET username = ?, first_name = ?, last_name = ?
                WHERE user_id = ?
            ''', (username, first_name, last_name, user_id))
        else:
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, last_name, joined_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name))
        conn.commit()

def get_user(user_id: int) -> Dict:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        else:
            return {
                'user_id': user_id, 'username': None, 'first_name': None, 'last_name': None,
                'joined_at': None, 'is_subscribed': 0, 'invites_count': 0,
                'exempt_from_invites': 0, 'blocked': 0, 'referrer_id': None,
                'invite_message_shown': 0, 'invite_rewarded': 0
            }

def set_user_blocked(user_id: int, blocked: bool = True):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET blocked = ? WHERE user_id = ?', (1 if blocked else 0, user_id))
        conn.commit()

def set_user_exempt(user_id: int, exempt: bool = True):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET exempt_from_invites = ? WHERE user_id = ?', (1 if exempt else 0, user_id))
        conn.commit()

def increment_invites(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET invites_count = invites_count + 1 WHERE user_id = ?', (user_id,))
        conn.commit()

def set_referrer(user_id: int, referrer_id: int):
    if user_id == referrer_id:
        return
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row and row['referrer_id'] is not None:
            return
        cursor.execute('UPDATE users SET referrer_id = ? WHERE user_id = ?', (referrer_id, user_id))
        conn.commit()

def set_invite_message_shown(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET invite_message_shown = 1 WHERE user_id = ?', (user_id,))
        conn.commit()

def mark_invite_rewarded(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET invite_rewarded = 1 WHERE user_id = ?', (user_id,))
        conn.commit()

def get_all_users_ids() -> List[int]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        return [row['user_id'] for row in cursor.fetchall()]

# --- دوال الكورسات والفيديوهات ---
def get_courses() -> List[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM courses ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]

def get_videos(course_id: int) -> List[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, file_id, message_id, video_order
            FROM videos
            WHERE course_id=?
            ORDER BY video_order
        ''', (course_id,))
        return [dict(row) for row in cursor.fetchall()]

def add_course(name: str) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO courses (name) VALUES (?)', (name,))
        conn.commit()
        return cursor.lastrowid

def delete_course(course_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM courses WHERE id=?', (course_id,))
        conn.commit()

def add_video(course_id: int, file_id: str, message_id: int, video_order: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO videos (course_id, file_id, message_id, video_order)
            VALUES (?, ?, ?, ?)
        ''', (course_id, file_id, message_id, video_order))
        conn.commit()

# --- دوال معرض الإنجازات ---
def add_achievement(type_: str, content: str, caption: str = ""):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO achievements (type, content, caption)
            VALUES (?, ?, ?)
        ''', (type_, content, caption))
        conn.commit()

def get_achievements() -> List[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM achievements ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]

def delete_achievement(achievement_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM achievements WHERE id=?', (achievement_id,))
        conn.commit()

# --- دوال المداد (مقالات) ---
def add_article(title: str, content: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO articles (title, content)
            VALUES (?, ?)
        ''', (title, content))
        conn.commit()

def get_articles() -> List[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM articles ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]

def delete_article(article_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM articles WHERE id=?', (article_id,))
        conn.commit()

# --- دوال الإعدادات ---
def get_setting(key: str, default: str = None) -> str:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row['value'] if row else default

def set_setting(key: str, value: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
        conn.commit()

def is_invite_system_enabled() -> bool:
    return get_setting('invite_system_enabled', 'true').lower() == 'true'
