
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from database import get_channels


def participation_keyboard():
    buttons = []

    for chat_id, username, title in get_channels():
        buttons.append([
            InlineKeyboardButton(
                text=f"📢 {title or '@' + username}",
                url=f"https://t.me/{username}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="✅ Проверить подписки",
            callback_data="check_subscription"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_keyboard(active_giveaway=True):
    buttons = []

    if active_giveaway:
        buttons.extend([
            [
                InlineKeyboardButton(
                    text="👥 Участники",
                    callback_data="admin_count"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎲 Выбрать победителя",
                    callback_data="admin_draw"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 Список победителей",
                    callback_data="admin_winners"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏹ Завершить розыгрыш",
                    callback_data="admin_finish"
                )
            ]
        ])

    else:
        buttons.append([
            InlineKeyboardButton(
                text="➕ Создать новый розыгрыш",
                callback_data="admin_create"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="📚 История розыгрышей",
            callback_data="admin_history"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
