pip install aiogram apscheduler
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

API_TOKEN = "7204826876:AAHRWBxS0H8bRRe89S_-F3eAN7q8yX71rk0"
ADMIN_ID = @JermYong  # Replace with your Telegram user ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()
pending_posts = {}  # user_id: {"text": ..., "msg_id": ...}

@dp.message_handler()
async def receive_submission(message: types.Message):
    # Store user's submission for review
    pending_posts[message.from_user.id] = {"text": message.text, "msg_id": message.message_id}
    # Forward to admin
    await bot.send_message(ADMIN_ID, f"New submission from {message.from_user.id}:\n{message.text}")
    await message.reply("Submission received! Await admin review.")

# Add more handlers for approval etc.
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID)
async def admin_commands(message: types.Message):
    if message.text.startswith("/approve"):
        user_id = int(message.text.split()[13])
        await message.reply("Please send schedule time in format 'YYYY-MM-DD HH:MM'")
        # Store which post is being scheduled
        dp.current_state(user=ADMIN_ID).set_data({"user_id": user_id})
    elif message.text.startswith("/reject"):
        user_id = int(message.text.split()[13])
        await bot.send_message(user_id, "Your submission was rejected.")
        
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID)
async def get_schedule_time(message: types.Message):
    # Parse time and schedule post
    data = await dp.current_state(user=ADMIN_ID).get_data()
    user_id = data["user_id"]
    text = pending_posts[user_id]["text"]
    time_str = message.text
    from datetime import datetime
    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    scheduler.add_job(send_to_channel, "date", run_date=dt, args=[text, user_id])
    await bot.send_message(user_id, f"Your post will be published at {time_str}.")
    await message.reply("Post scheduled.")

async def send_to_channel(text, user_id):
    await bot.send_message("@YourChannelUsername", text)
    await bot.send_message(user_id, "Your post was published!")

if __name__ == "__main__":
    scheduler.start()
    executor.start_polling(dp, skip_updates=True)

