"""
ui.py
=====
统一管理所有"面板"（一条消息 + 一组 inline 按钮）。

设计原则（对应需求 4、5）：
  - 所有功能只通过 inline 按钮触发，不依赖聊天框斜杠命令
    （/start 除外，它是打开面板的入口）。
  - 每次响应尽量"编辑"同一条消息来切换面板，而不是删除重发，
    减少一次删除+一次发送的 API 调用，观感也更连贯。
  - Telegram 官方 Bot 消息不支持自定义文字颜色（无论 HTML 还是 Markdown
    都没有 color 属性），"大一点、有颜色"在 Telegram 里只能通过
    加粗 / 分隔线 / emoji 色块 / blockquote 来模拟视觉层次，
    这里统一封装成 header()/divider() 帮助函数。
"""

from telebot import types

# ---------------------------------------------------------
# 视觉样式帮助函数（用 emoji + 排版模拟"大、彩色"效果）
# ---------------------------------------------------------

def header(title: str, emoji: str = "🔷") -> str:
    return f"{emoji} <b>{title}</b> {emoji}\n" + ("━" * 16)


def divider() -> str:
    return "─" * 16


def kb(rows):
    """
    rows: list[list[(text, callback_data)]] 或 list[list[types.InlineKeyboardButton]]
    快速构建 InlineKeyboardMarkup。
    """
    markup = types.InlineKeyboardMarkup(row_width=2)
    for row in rows:
        buttons = []
        for item in row:
            if isinstance(item, types.InlineKeyboardButton):
                buttons.append(item)
            else:
                text, data = item
                buttons.append(types.InlineKeyboardButton(text, callback_data=data))
        markup.row(*buttons)
    return markup


def url_button_row(text, url):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text, url=url))
    return markup


# ---------------------------------------------------------
# 面板渲染：优先编辑已有消息，编辑失败（比如消息太旧）再发新的
# ---------------------------------------------------------

def render(bot, chat_id, message_id, text, markup, parse_mode="HTML"):
    if message_id:
        try:
            bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
            return message_id
        except Exception:
            pass  # 消息内容没变化 / 消息已过期，走下面发新消息兜底

    sent = bot.send_message(
        chat_id, text, reply_markup=markup, parse_mode=parse_mode,
        disable_web_page_preview=True,
    )
    return sent.message_id
