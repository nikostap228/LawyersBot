
import html
import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import ADMIN_IDS
from database import (
    add_channel,
    remove_channel,
    get_channels,
    add_participant,
    get_participants_count,
    is_registration_closed,
    draw_winner,
    get_winners,
    get_winners_count
)

from keyboards import (
    participation_keyboard,
    admin_keyboard
)

router = Router()


def is_admin(user_id):
    return user_id in ADMIN_IDS


# -------------------------
# ПРОВЕРКА ПОДПИСОК
# -------------------------

async def check_subscription(bot, user_id):

    channels = get_channels()

    if not channels:
        return False

    for chat_id, username, title in channels:

        try:
            member = await bot.get_chat_member(
                chat_id=chat_id,
                user_id=user_id
            )

            if member.status not in [
                "creator",
                "administrator",
                "member"
            ] and not (
                member.status == "restricted"
                and member.is_member
            ):
                return False

        except TelegramBadRequest:
            logging.exception(
                "Не удалось проверить канал: %s",
                username
            )
            return False

    return True


# -------------------------
# СТАРТ
# -------------------------

@router.message(CommandStart())
async def start(message: Message):

    if is_registration_closed():
        await message.answer(
            "⛔ Регистрация на розыгрыш завершена."
        )
        return

    if not get_channels():
        await message.answer(
            "⏳ Организатор ещё не добавил каналы."
        )
        return

    await message.answer(
        "🎁 ДОБРО ПОЖАЛОВАТЬ В РОЗЫГРЫШ!\n\n"
        "Для участия подпишитесь на все каналы ниже.\n\n"
        "После подписки нажмите кнопку проверки.",
        reply_markup=participation_keyboard()
    )


# -------------------------
# РЕГИСТРАЦИЯ
# -------------------------

@router.callback_query(F.data == "check_subscription")
async def check_subscription_handler(callback: CallbackQuery):

    user = callback.from_user

    if is_registration_closed():
        await callback.answer(
            "Регистрация уже завершена!",
            show_alert=True
        )
        return

    subscribed = await check_subscription(
        callback.bot,
        user.id
    )

    if not subscribed:
        await callback.answer(
            "Вы подписаны не на все каналы!",
            show_alert=True
        )
        return

    added = add_participant(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name
    )

    count = get_participants_count()

    if added:
        text = (
            "🎉 ВЫ УЧАСТВУЕТЕ В РОЗЫГРЫШЕ!\n\n"
            "Ваша регистрация успешно завершена.\n\n"
            f"👥 Участников: {count}"
        )
    else:
        text = (
            "ℹ️ Вы уже зарегистрированы!\n\n"
            f"👥 Участников: {count}"
        )

    await callback.message.edit_text(text)
    await callback.answer("Готово!")


# -------------------------
# ПОЛУЧЕНИЕ TELEGRAM ID
# -------------------------

@router.message(Command("id"))
async def get_id(message: Message):

    await message.answer(
        f"Ваш Telegram ID: {message.from_user.id}"
    )


# -------------------------
# ДОБАВЛЕНИЕ КАНАЛА
# -------------------------

@router.message(Command("addchannel"))
async def add_channel_handler(message: Message):

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    if is_registration_closed():
        await message.answer(
            "Регистрация уже закрыта. "
            "Нельзя менять список каналов текущего розыгрыша."
        )
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Использование:\n"
            "/addchannel @username"
        )
        return

    username = parts[1].strip()

    if not username.startswith("@"):
        await message.answer(
            "Укажи публичный канал через @username."
        )
        return

    try:
        chat = await message.bot.get_chat(username)

        if chat.type != "channel" or not chat.username:
            await message.answer(
                "Это не публичный Telegram-канал."
            )
            return

        bot_member = await message.bot.get_chat_member(
            chat_id=chat.id,
            user_id=(await message.bot.get_me()).id
        )

        if bot_member.status not in ["administrator", "creator"]:
            await message.answer(
                "Сначала добавь бота администратором канала."
            )
            return

        added = add_channel(
            chat_id=chat.id,
            username=chat.username,
            title=chat.title
        )

        if added:
            await message.answer(
                f"✅ Канал добавлен!\n\n"
                f"Название: {html.escape(chat.title)}\n"
                f"Ссылка: https://t.me/{chat.username}\n\n"
                f"Всего каналов: {len(get_channels())}"
            )
        else:
            await message.answer(
                "Этот канал уже добавлен."
            )

    except TelegramBadRequest:
        await message.answer(
            "Не удалось найти канал или проверить права бота. "
            "Проверь username и права администратора."
        )


# -------------------------
# УДАЛЕНИЕ КАНАЛА
# -------------------------

@router.message(Command("removechannel"))
async def remove_channel_handler(message: Message):

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    if is_registration_closed():
        await message.answer(
            "Регистрация уже закрыта. "
            "Нельзя менять каналы текущего розыгрыша."
        )
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Использование:\n"
            "/removechannel @username"
        )
        return

    username = parts[1].replace("@", "").lower()

    if remove_channel(username):
        await message.answer(
            f"✅ Канал @{username} удалён."
        )
    else:
        await message.answer(
            "Такого канала нет в списке."
        )


# -------------------------
# СПИСОК КАНАЛОВ
# -------------------------

@router.message(Command("channels"))
async def channels_handler(message: Message):

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    channels = get_channels()

    if not channels:
        await message.answer("Каналы ещё не добавлены.")
        return

    text = "📢 ОБЯЗАТЕЛЬНЫЕ КАНАЛЫ:\n\n"

    for index, (chat_id, username, title) in enumerate(
        channels, start=1
    ):
        text += (
            f"{index}. {html.escape(title or username)}\n"
            f"https://t.me/{username}\n\n"
        )

    await message.answer(text)


# -------------------------
# ПАНЕЛЬ АДМИНИСТРАТОРА
# -------------------------

@router.message(Command("admin"))
async def admin_panel(message: Message):

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    status = (
        "Закрыта"
        if is_registration_closed()
        else "Открыта"
    )

    await message.answer(
        "🛠 ПАНЕЛЬ АДМИНИСТРАТОРА\n\n"
        f"👥 Участников: {get_participants_count()}\n"
        f"🏆 Победителей: {get_winners_count()}\n"
        f"📢 Каналов: {len(get_channels())}\n"
        f"📝 Регистрация: {status}",
        reply_markup=admin_keyboard()
    )


# -------------------------
# КОЛИЧЕСТВО УЧАСТНИКОВ
# -------------------------

@router.callback_query(F.data == "admin_count")
async def admin_count(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await callback.answer(
        f"Участников: {get_participants_count()}",
        show_alert=True
    )


# -------------------------
# ВЫБОР ПОБЕДИТЕЛЯ
# -------------------------

@router.callback_query(F.data == "admin_draw")
async def admin_draw(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    winner, status = draw_winner()

    if status == "empty":
        await callback.answer(
            "Больше нет участников для выбора!",
            show_alert=True
        )
        return

    if status != "success":
        await callback.answer(
            "Ошибка выбора победителя.",
            show_alert=True
        )
        return

    user_id, username, full_name = winner

    if username:
        telegram_user = f"@{html.escape(username)}"
    else:
        telegram_user = (
            f'<a href="tg://user?id={user_id}">'
            f'{html.escape(full_name)}</a>'
        )

    result = (
        "🏆 <b>НОВЫЙ ПОБЕДИТЕЛЬ!</b>\n\n"
        f"👤 Имя: {html.escape(full_name)}\n"
        f"📱 Telegram: {telegram_user}\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"👥 Всего участников: {get_participants_count()}\n"
        f"🏆 Победителей: {get_winners_count()}\n\n"
        "🎉 Поздравляем!"
    )

    await callback.message.answer(
        result,
        parse_mode="HTML"
    )

    await callback.answer(
        "Новый победитель выбран!"
    )


# -------------------------
# СПИСОК ПОБЕДИТЕЛЕЙ
# -------------------------

@router.callback_query(F.data == "admin_winners")
async def admin_winners_button(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await send_winners(callback.message)
    await callback.answer()


@router.message(Command("winners"))
async def winners_command(message: Message):

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    await send_winners(message)


async def send_winners(message):

    winners = get_winners()

    if not winners:
        await message.answer(
            "🏆 Победителей пока нет."
        )
        return

    text = "🏆 <b>СПИСОК ПОБЕДИТЕЛЕЙ</b>\n\n"

    for index, (user_id, username, full_name, selected_at) in enumerate(
        winners, start=1
    ):

        if username:
            contact = f"@{html.escape(username)}"
        else:
            contact = (
                f'<a href="tg://user?id={user_id}">'
                f'{html.escape(full_name)}</a>'
            )

        text += (
            f"<b>{index}. {html.escape(full_name)}</b>\n"
            f"Telegram: {contact}\n\n"
        )

    await message.answer(
        text,
        parse_mode="HTML"
    )
