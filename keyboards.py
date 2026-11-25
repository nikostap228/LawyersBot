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

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


def admin_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
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
            ]
        ]
    )