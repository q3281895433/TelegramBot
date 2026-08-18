import os
import threading
from datetime import datetime

LOG_FILE = "logs/user_actions.log"
LOG_LOCK = threading.Lock()


def ensure_log_dir():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)


def log_action(user_id, action, details="", balance_change=0):
    """
    记录用户操作。
    action: 'query' / 'recharge' / 'admin' 等
    details: 附加信息
    balance_change: 余额变化（正为增加，负为消耗）
    """
    ensure_log_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} | UID:{user_id} | {action} | {details} | 余额变化:{balance_change}\n"
    with LOG_LOCK:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)