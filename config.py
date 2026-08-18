"""
config.py
=========
统一读取环境变量。
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------
# Telegram
# ---------------------------------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("没有找到 BOT_TOKEN，请在 .env 中配置")

# 如需走本地代理，取消下面的注释并按需修改
# PROXY = {"https": "http://127.0.0.1:7877"}
PROXY = None

# ---------------------------------------------------------
# 管理员
# ---------------------------------------------------------

_admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = set()
for _item in _admin_raw.split(","):
    _item = _item.strip()
    if not _item:
        continue
    try:
        ADMIN_IDS.add(int(_item))
    except ValueError:
        pass


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------------------------------------------------------
# 数据库
# ---------------------------------------------------------

DB_PATH = os.getenv("DB_PATH", "bot_data.db")

# ---------------------------------------------------------
# 积分（只有"付费查询"消耗积分；免费查询永远不扣分）
# ---------------------------------------------------------

# 1 USDT 兑换多少积分
USDT_TO_POINTS = int(os.getenv("USDT_TO_POINTS", "7"))

# OKPay 充值 1 单位金额兑换多少积分（按你 OKPay 结算币种自行调整）
OKPAY_TO_POINTS = int(os.getenv("OKPAY_TO_POINTS", "7"))

# 邀请一个新用户，邀请人获得多少积分奖励（0 表示不奖励）
INVITE_REWARD_POINTS = int(os.getenv("INVITE_REWARD_POINTS", "2"))

# ---------------------------------------------------------
# 支付通用配置
# ---------------------------------------------------------

USDT_ADDRESS_POOL_RAW = os.getenv("USDT_RECEIVE_ADDRESS_POOL", "")
USDT_ADDRESS_POOL = [a.strip() for a in USDT_ADDRESS_POOL_RAW.split(",") if a.strip()]

USDT_JETTON_MASTER = os.getenv(
    "USDT_JETTON_MASTER",
    "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs",
)

TONCENTER_API_KEY = os.getenv("TONCENTER_API_KEY", "")
TONCENTER_API_URL = "https://toncenter.com/api/v3/jetton/transfers"

MIN_ORDER_AMOUNT = float(os.getenv("MIN_ORDER_AMOUNT", "1"))
PAYMENT_EXPIRE_MINUTES = int(os.getenv("PAYMENT_EXPIRE_MINUTES", "30"))
AUTO_SCAN_INTERVAL_SECONDS = int(os.getenv("AUTO_SCAN_INTERVAL_SECONDS", "30"))

# ---------------------------------------------------------
# OKPay（按官方文档《OKPay 商户对接文档(完整版·HMAC-SHA256新协议)》）
# 文档地址：https://docs.okaypay.me/doc.html
# ---------------------------------------------------------

# id (App ID)：商户标识，随每个请求明文提交
OKPAY_APP_ID = os.getenv("OKPAY_APP_ID", "")

# token (密钥)：仅用于本地计算 HMAC-SHA256 签名，绝不随请求传输，务必保密
OKPAY_APP_TOKEN = os.getenv("OKPAY_APP_TOKEN", "")

# 接口根地址 + 前缀（文档 1. 基本信息：根地址 https://api.okaypay.me，前缀 /shop）
OKPAY_API_ROOT = os.getenv("OKPAY_API_ROOT", "https://api.okaypay.me")
OKPAY_API_PREFIX = os.getenv("OKPAY_API_PREFIX", "/shop")

# 注意：创建订单固定使用 POST /shop/payLink（文档 6.1 节），
# 已在 payment.py 里写死，不再需要单独配置路径。

# 支付成功后 OKPay 异步通知你服务器的回调地址（你自己的服务器要能被公网访问到，
# 必须是合法的公网 http/https 地址，否则 payLink 会报错 "callback_url 参数验证失败"）
OKPAY_NOTIFY_URL = os.getenv("OKPAY_NOTIFY_URL", "")
# 用户支付完成后，机器人内"返回"按钮跳转回的地址（可选）
OKPAY_REDIRECT_URL = os.getenv("OKPAY_REDIRECT_URL", "")

TIMEZONE_OFFSET_HOURS = int(os.getenv("TZ_OFFSET_HOURS", "8"))

# 广播：每发送一条消息之间的间隔秒数，避免触发 Telegram 限流
BROADCAST_INTERVAL_SECONDS = float(os.getenv("BROADCAST_INTERVAL_SECONDS", "0.05"))
