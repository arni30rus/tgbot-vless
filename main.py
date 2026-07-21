import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from config import BOT_TOKEN
from database import init_db
from handlers import user, admin
from aiogram.fsm.storage.memory import MemoryStorage


logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    # инициализация БД
    await init_db()
    
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())
    
    # ссылки на хендлеры
    dp.include_router(user.router)
    dp.include_router(admin.router)
    
    # удаляем вебхуки, запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
