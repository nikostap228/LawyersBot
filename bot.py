import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import init_db
from handlers import router


async def main():

    logging.basicConfig(
        level=logging.INFO
    )

    bot = Bot(token=BOT_TOKEN)

    dp = Dispatcher()

    init_db()

    dp.include_router(router)

    print("🤖 Giveaway Bot запущен!")

    try:
        await dp.start_polling(bot)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())