import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

def get_api_key(path="/etc/secrets/API_KEY"):
    with open(path, "r") as f:
        return f.read().strip()
def get_user_id(path="/etc/secrets/Telegram_ID"):
    with open(path, "r") as f:
        return int(f.read().strip())
API_TOKEN = get_api_key()
ADMIN_ID = get_user_id() 

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()
pending_posts = {}  # user_id: {"text": ..., "msg_id": ...}

@dp.message_handler()
async def receive_submission(message: types.Message):
    user_id = message.from_user.id
    # Store user's submission for review
    pending_posts[user_id] = {"text": message.text, "msg_id": message.message_id}
    # Forward to admin
    await bot.send_message(ADMIN_ID, f"New submission from {user_id}:\n{message.text}")
    await message.reply("Submission received! Await admin review.")

# Admin commands handler
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID)
async def admin_commands(message: types.Message):
    if message.text.startswith("/approve"):
        parts = message.text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            user_id = int(parts[1])
            await message.reply("Please send schedule time in format 'YYYY-MM-DD HH:MM'")
            # Save state with user_id
            state = dp.current_state(chat=message.chat.id, user=ADMIN_ID)
            await state.update_data(user_id=user_id)
        else:
            await message.reply("Usage: /approve <user_id>")
    elif message.text.startswith("/reject"):
        parts = message.text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            user_id = int(parts[1])
            await bot.send_message(user_id, "Your submission was rejected.")
            await message.reply(f"Submission from {user_id} rejected.")
        else:
            await message.reply("Usage: /reject <user_id>")

# Handle schedule time input from admin
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID)
async def get_schedule_time(message: types.Message):
    state = dp.current_state(chat=message.chat.id, user=ADMIN_ID)
    data = await state.get_data()
    user_id = data.get("user_id")
    if not user_id:
        return  # No pending approval scheduling

    text = pending_posts.get(user_id, {}).get("text")
    if not text:
        await message.reply("No submission found for this user.")
        return

    time_str = message.text
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.reply("Invalid date/time format. Use 'YYYY-MM-DD HH:MM'")
        return

    def send_to_channel(text, user_id):
        asyncio.create_task(bot.send_message("@YourChannelUsername", text))
        asyncio.create_task(bot.send_message(user_id, "Your post was published!"))

    scheduler.add_job(send_to_channel, "date", run_date=dt, args=[text, user_id])
    await bot.send_message(user_id, f"Your post will be published at {time_str}.")
    await message.reply("Post scheduled.")

if __name__ == "__main__":
    scheduler.start()
    executor.start_polling(dp, skip_updates=True)

