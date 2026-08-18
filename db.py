"""
db.py
=====
SQLite 数据层。

关键设计（对应"只有付费查询才有积分制度"）：
  - users.points 是唯一的一种积分，只在"付费查询"里被消耗，
    免费查询模块永远不会调用扣分逻辑。
  - 积分只有两个来源：充值（USDT/OKPay）、管理员手动发放、邀请奖励。
"""

import random
import string
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import config

_LOCK = threading.Lock()
TZ = timezone(timedelta(hours=config.TIMEZONE_OFFSET_HOURS))


def _conn():
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    with _LOCK, _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                points INTEGER NOT NULL DEFAULT 0,
                banned INTEGER NOT NULL DEFAULT 0,
                ban_reason TEXT,
                invite_code TEXT UNIQUE,
                invited_by INTEGER,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS addresses (
                address TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                order_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                method TEXT NOT NULL,
                receive_target TEXT NOT NULL,
                expected_amount REAL NOT NULL,
                paid_amount REAL,
                points_credit INTEGER,
                tx_hash TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _gen_invite_code(conn):
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        exists = conn.execute(
            "SELECT 1 FROM users WHERE invite_code=?", (code,)
        ).fetchone()
        if not exists:
            return code


# ---------------------------------------------------------
# 用户
# ---------------------------------------------------------

def get_or_create_user(user_id, username, invite_code_used=None):
    with _LOCK, _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row:
            if username and row["username"] != username:
                conn.execute(
                    "UPDATE users SET username=? WHERE user_id=?", (username, user_id)
                )
                conn.commit()
            return dict(row)

        invite_code = _gen_invite_code(conn)

        invited_by = None
        if invite_code_used:
            inviter = conn.execute(
                "SELECT user_id FROM users WHERE invite_code=?", (invite_code_used,)
            ).fetchone()
            if inviter and inviter["user_id"] != user_id:
                invited_by = inviter["user_id"]

        conn.execute(
            """
            INSERT INTO users (user_id, username, points, invite_code, invited_by, created_at)
            VALUES (?,?,0,?,?,?)
            """,
            (user_id, username, invite_code, invited_by, now_str()),
        )
        conn.commit()

        new_user = dict(
            conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        )

    # 邀请奖励（新用户创建成功后，在锁外面发放，避免嵌套加锁）
    if invited_by and config.INVITE_REWARD_POINTS:
        add_points(invited_by, config.INVITE_REWARD_POINTS, f"邀请奖励(新用户{user_id})")

    return new_user


def get_user(user_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_invite_code(code):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE invite_code=?", (code,)).fetchone()
        return dict(row) if row else None


def get_invite_count(user_id):
    with _conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) c FROM users WHERE invited_by=?", (user_id,)
        ).fetchone()["c"]


def is_banned(user_id):
    user = get_user(user_id)
    return bool(user and user["banned"])


def set_ban(user_id, banned: bool, reason: str = ""):
    with _LOCK, _conn() as conn:
        conn.execute(
            "UPDATE users SET banned=?, ban_reason=? WHERE user_id=?",
            (1 if banned else 0, reason, user_id),
        )
        conn.commit()


def add_points(user_id, delta, reason=""):
    """delta 可正可负，返回更新后的积分。免费查询模块不应调用此函数。"""
    with _LOCK, _conn() as conn:
        conn.execute("UPDATE users SET points = points + ? WHERE user_id=?", (delta, user_id))
        conn.commit()
        row = conn.execute("SELECT points FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row["points"] if row else None


def list_users(limit=50, offset=0):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def list_all_user_ids():
    with _conn() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
        return [r["user_id"] for r in rows]


def count_users():
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]


# ---------------------------------------------------------
# 收款地址池（USDT）
# ---------------------------------------------------------

def init_address_pool(addresses):
    with _LOCK, _conn() as conn:
        for addr in addresses:
            conn.execute(
                "INSERT OR IGNORE INTO addresses (address, enabled) VALUES (?, 1)", (addr,)
            )
        conn.commit()


def add_address(address):
    with _LOCK, _conn() as conn:
        existing = conn.execute("SELECT * FROM addresses WHERE address=?", (address,)).fetchone()
        if existing:
            conn.execute("UPDATE addresses SET enabled=1 WHERE address=?", (address,))
            conn.commit()
            return True, "地址已存在，已重新启用。"
        conn.execute("INSERT INTO addresses (address, enabled) VALUES (?, 1)", (address,))
        conn.commit()
        return True, "地址已添加。"


def remove_address(address):
    with _LOCK, _conn() as conn:
        cur = conn.execute("UPDATE addresses SET enabled=0 WHERE address=?", (address,))
        conn.commit()
        return cur.rowcount > 0


def list_addresses():
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM addresses").fetchall()
        result = []
        for row in rows:
            pending = conn.execute(
                "SELECT COUNT(*) c FROM payments WHERE receive_target=? AND status='pending'",
                (row["address"],),
            ).fetchone()["c"]
            result.append(
                {"address": row["address"], "enabled": row["enabled"], "pending_count": pending}
            )
        return result


def get_available_address():
    with _conn() as conn:
        rows = conn.execute("SELECT address FROM addresses WHERE enabled=1").fetchall()
        if not rows:
            return None
        best_addr, best_count = None, None
        for row in rows:
            addr = row["address"]
            pending = conn.execute(
                "SELECT COUNT(*) c FROM payments WHERE receive_target=? AND status='pending'",
                (addr,),
            ).fetchone()["c"]
            if best_count is None or pending < best_count:
                best_addr, best_count = addr, pending
        return best_addr


# ---------------------------------------------------------
# 支付订单
# ---------------------------------------------------------

def create_payment(order_id, user_id, method, receive_target, expected_amount):
    expires_at = (
        datetime.now(TZ) + timedelta(minutes=config.PAYMENT_EXPIRE_MINUTES)
    ).strftime("%Y-%m-%d %H:%M:%S")
    with _LOCK, _conn() as conn:
        conn.execute(
            """
            INSERT INTO payments
                (order_id, user_id, method, receive_target, expected_amount,
                 status, created_at, expires_at)
            VALUES (?,?,?,?,?, 'pending', ?, ?)
            """,
            (order_id, user_id, method, receive_target, expected_amount, now_str(), expires_at),
        )
        conn.commit()


def get_payment(order_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM payments WHERE order_id=?", (order_id,)).fetchone()
        return dict(row) if row else None


def confirm_payment(order_id, paid_amount, points_credit, tx_hash):
    with _LOCK, _conn() as conn:
        try:
            cur = conn.execute(
                """
                UPDATE payments
                SET status='confirmed', paid_amount=?, points_credit=?, tx_hash=?
                WHERE order_id=? AND status='pending'
                """,
                (paid_amount, points_credit, tx_hash, order_id),
            )
            conn.commit()
            return cur.rowcount > 0
        except sqlite3.IntegrityError:
            return False


def cancel_payment(order_id):
    with _LOCK, _conn() as conn:
        cur = conn.execute(
            "UPDATE payments SET status='cancelled' WHERE order_id=? AND status='pending'",
            (order_id,),
        )
        conn.commit()
        return cur.rowcount > 0


def expire_pending_payments():
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT order_id FROM payments WHERE status='pending' AND expires_at < ?",
            (now_str(),),
        ).fetchall()
        ids = [r["order_id"] for r in rows]
        if ids:
            conn.executemany(
                "UPDATE payments SET status='expired' WHERE order_id=?", [(i,) for i in ids]
            )
            conn.commit()
        return ids


def get_all_pending_payments():
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM payments WHERE status='pending'").fetchall()
        return [dict(r) for r in rows]
