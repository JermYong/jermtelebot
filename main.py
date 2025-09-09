import asyncio
import logging
from TeleBot import dp, bot  # Import your Dispatcher and Bot objects from telebot.py

async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())