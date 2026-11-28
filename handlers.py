
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
    get_active_giveaway,
    create_giveaway,
    finish_giveaway,
    get_giveaways_history,
    add_participant,
    get_participants_count,
    is_registration_closed,
    draw_winner,
    get_winners,
    get_winners_count
)

from keyboards import (
    participation_keyboard,
    admin_keyboard,
    user_keyboard,
    finish_confirmation_keyboard
)

router = Router()


def is_admin(user_id):
    return user_id in ADMIN_IDS


# -------------------------
# СТАРТ
# -------------------------


async def start_handler(message: Message):

    await message.answer(
        "👋 Добро пожаловать!\n"
        "Нажмите «🚀 Старт», чтобы открыть участие в розыгрыше.",
        reply_markup=user_keyboard()
    )

    giveaway = get_active_giveaway()

    if not giveaway:
        await message.answer(
            "⏳ Сейчас нет активного розыгрыша."
        )
        return

    if giveaway[2]:
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


@router.message(CommandStart())
async def start_command(message: Message):
    await start_handler(message)


@router.message(F.text == "🚀 Старт")
async def start_button(message: Message):
    await start_handler(message)


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
# TELEGRAM ID
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
            "Регистрация закрыта или активного розыгрыша нет. "
            "Сначала создай новый розыгрыш."
        )
        return

    parts = (message.text or "").split()

    if len(parts) != 2 or not parts[1].startswith("@"):
        await message.answer(
            "Использование:\n/addchannel @username"
        )
        return

    username = parts[1].strip()

    try:
        chat = await message.bot.get_chat(username)

        if chat.type != "channel" or not chat.username:
            await message.answer("Это не публичный Telegram-канал.")
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
                f"✅ Канал добавлен!\n"
                f"Название: {html.escape(chat.title or '')}\n"
                f"Ссылка: https://t.me/{chat.username}\n"
                f"Всего каналов: {len(get_channels())}"
            )
        else:
            await message.answer("Этот канал уже добавлен.")

    except TelegramBadRequest:
        await message.answer(
            "Не удалось найти канал или проверить права бота."
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
            "Регистрация закрыта или активного розыгрыша нет."
        )
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer("Использование:\n/removechannel @username")
        return

    username = parts[1].replace("@", "").lower()

    if remove_channel(username):
        await message.answer(f"✅ Канал @{username} удалён.")
    else:
        await message.answer("Такого канала нет в списке.")


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

async def show_admin_panel(message: Message):

    giveaway = get_active_giveaway()
    active = giveaway is not None

    if active:
        status = "Закрыта" if giveaway[2] else "Открыта"
        giveaway_id = giveaway[0]
        participants = get_participants_count(giveaway_id)
        winners = get_winners_count(giveaway_id)
    else:
        status = "Нет активного розыгрыша"
        participants = 0
        winners = 0

    await message.answer(
        "🛠 ПАНЕЛЬ АДМИНИСТРАТОРА\n\n"
        f"👥 Участников: {participants}\n"
        f"🏆 Победителей: {winners}\n"
        f"📢 Каналов: {len(get_channels())}\n"
        f"📝 Регистрация: {status}",
        reply_markup=admin_keyboard(active_giveaway=active)
    )


@router.message(Command("admin"))
async def admin_panel(message: Message):

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return

    await show_admin_panel(message)


# -------------------------
# КОЛИЧЕСТВО УЧАСТНИКОВ
# -------------------------

@router.callback_query(F.data == "admin_count")
async def admin_count(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    giveaway = get_active_giveaway()

    if not giveaway:
        await callback.answer("Нет активного розыгрыша.", show_alert=True)
        return

    count = get_participants_count(giveaway[0])

    await callback.answer(
        f"Участников: {count}",
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
            "Нет активного розыгрыша.",
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

    giveaway = get_active_giveaway()
    giveaway_id = giveaway[0] if giveaway else None

    result = (
        "🏆 <b>НОВЫЙ ПОБЕДИТЕЛЬ!</b>\n\n"
        f"👤 Имя: {html.escape(full_name)}\n"
        f"📱 Telegram: {telegram_user}\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"👥 Всего участников: {get_participants_count(giveaway_id)}\n"
        f"🏆 Победителей: {get_winners_count(giveaway_id)}\n\n"
        "🎉 Поздравляем!"
    )

    await callback.message.answer(result, parse_mode="HTML")
    await callback.answer("Новый победитель выбран!")


# -------------------------
# ПОБЕДИТЕЛИ
# -------------------------

async def send_winners(message):

    giveaway = get_active_giveaway()

    if not giveaway:
        await message.answer("Сейчас нет активного розыгрыша.")
        return

    winners = get_winners(giveaway[0])

    if not winners:
        await message.answer("🏆 Победителей пока нет.")
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

    await message.answer(text, parse_mode="HTML")


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


# -------------------------
# ЗАВЕРШЕНИЕ РОЗЫГРЫША
# -------------------------

@router.callback_query(F.data == "admin_finish")
async def admin_finish(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    if not get_active_giveaway():
        await callback.answer(
            "Нет активного розыгрыша.",
            show_alert=True
        )
        return

    await callback.message.answer(
        "⚠️ Ты действительно хочешь завершить этот розыгрыш?\n\n"
        "После завершения создать новый розыгрыш можно будет "
        "через панель администратора.",
        reply_markup=finish_confirmation_keyboard()
    )

    await callback.answer()


@router.callback_query(F.data == "admin_confirm_finish")
async def admin_confirm_finish(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    if not finish_giveaway():
        await callback.answer(
            "Не удалось завершить розыгрыш.",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        "✅ Розыгрыш успешно завершён!"
    )

    await callback.message.answer(
        "Теперь можно создать новый розыгрыш командой /admin.",
        reply_markup=admin_keyboard(active_giveaway=False)
    )

    await callback.answer("Розыгрыш завершён!")


@router.callback_query(F.data == "admin_cancel_finish")
async def admin_cancel_finish(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await callback.message.edit_text("❌ Завершение отменено.")
    await callback.answer()


# -------------------------
# СОЗДАНИЕ НОВОГО РОЗЫГРЫША
# -------------------------

@router.callback_query(F.data == "admin_create")
async def admin_create(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    giveaway_id = create_giveaway()

    if giveaway_id is None:
        await callback.answer(
            "Уже существует активный розыгрыш.",
            show_alert=True
        )
        return

    await callback.message.answer(
        f"🎉 Создан новый розыгрыш №{giveaway_id}!\n\n"
        "Регистрация открыта. Участники могут нажимать /start."
    )

    await callback.message.answer(
        "🛠 Панель администратора",
        reply_markup=admin_keyboard(active_giveaway=True)
    )

    await callback.answer("Новый розыгрыш создан!")


# -------------------------
# ИСТОРИЯ РОЗЫГРЫШЕЙ
# -------------------------

@router.callback_query(F.data == "admin_history")
async def admin_history(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    history = get_giveaways_history()

    if not history:
        await callback.message.answer(
            "📚 История розыгрышей пока пуста."
        )
        await callback.answer()
        return

    text = "📚 <b>ИСТОРИЯ РОЗЫГРЫШЕЙ</b>\n\n"

    for giveaway_id, status, created_at, completed_at in history:
        status_text = (
            "✅ Завершён"
            if status == "completed"
            else "🟢 Активен"
        )

        participants = get_participants_count(giveaway_id)
        winners = get_winners_count(giveaway_id)

        text += (
            f"<b>Розыгрыш №{giveaway_id}</b>\n"
            f"Статус: {status_text}\n"
            f"Участников: {participants}\n"
            f"Победителей: {winners}\n"
            f"Создан: {created_at}\n"
        )

        if completed_at:
            text += f"Завершён: {completed_at}\n"

        text += "\n"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
