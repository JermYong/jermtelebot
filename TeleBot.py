import os
import asyncio
from aiogram import Bot, Dispatcher, types
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
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()
pending_posts = {}  # user_id: {"text": ..., "msg_id": ...}

# Define states for FSM
class AdminStates(StatesGroup):
    waiting_for_schedule_time = State()

# Start scheduler
scheduler.start()

# Handler for regular user submissions
@dp.message(lambda message: message.from_user.id != ADMIN_ID)
async def receive_submission(message: types.Message):
    user_id = message.from_user.id
    # Store user's submission for review
    pending_posts[user_id] = {"text": message.text, "msg_id": message.message_id}
    
    # Forward to admin with inline keyboard for quick actions
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{user_id}")
        ]
    ])
    
    await bot.send_message(
        ADMIN_ID, 
        f"New submission from {user_id} (@{message.from_user.username or 'no_username'}):\n\n{message.text}",
        reply_markup=keyboard
    )
    await message.reply("✅ Submission received! Awaiting admin review.")

# Admin command handlers
@dp.message(Command("approve"))
async def approve_command(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) >= 2 and parts[1].isdigit():
        user_id = int(parts[1])
        await state.update_data(user_id=user_id)
        await state.set_state(AdminStates.waiting_for_schedule_time)
        await message.reply("📅 Please send schedule time in format 'YYYY-MM-DD HH:MM' or 'now' for immediate posting:")
    else:
        await message.reply("❌ Usage: /approve <user_id>")

@dp.message(Command("reject"))
async def reject_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) >= 2 and parts[1].isdigit():
        user_id = int(parts[1])
        if user_id in pending_posts:
            del pending_posts[user_id]
        await bot.send_message(user_id, "❌ Your submission was rejected.")
        await message.reply(f"✅ Submission from {user_id} rejected.")
    else:
        await message.reply("❌ Usage: /reject <user_id>")

# Callback handlers for inline buttons
@dp.callback_query(lambda c: c.data.startswith('approve_'))
async def approve_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback_query.data.split('_')[1])
    await state.update_data(user_id=user_id)
    await state.set_state(AdminStates.waiting_for_schedule_time)
    await callback_query.message.reply("📅 Please send schedule time in format 'YYYY-MM-DD HH:MM' or 'now' for immediate posting:")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith('reject_'))
async def reject_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback_query.data.split('_')[1])
    if user_id in pending_posts:
        del pending_posts[user_id]
    await bot.send_message(user_id, "❌ Your submission was rejected.")
    await callback_query.message.reply(f"✅ Submission from {user_id} rejected.")
    await callback_query.answer()

# Handle schedule time input from admin
@dp.message(AdminStates.waiting_for_schedule_time)
async def get_schedule_time(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    user_id = data.get("user_id")
    
    if not user_id or user_id not in pending_posts:
        await message.reply("❌ No pending submission found for this user.")
        await state.clear()
        return

    text = pending_posts[user_id].get("text")
    time_str = message.text.strip()

    # Handle immediate posting
    if time_str.lower() == "now":
        try:
            await bot.send_message(CHANNEL_USERNAME, text)
            await bot.send_message(user_id, "🎉 Your post has been published!")
            await message.reply("✅ Post published immediately.")
            del pending_posts[user_id]
        except Exception as e:
            await message.reply(f"❌ Error publishing post: {str(e)}")
        await state.clear()
        return

    # Handle scheduled posting
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        if dt <= datetime.now():
            await message.reply("❌ Scheduled time must be in the future.")
            return
    except ValueError:
        await message.reply("❌ Invalid date/time format. Use 'YYYY-MM-DD HH:MM' or 'now'")
        return

    async def send_to_channel(text, user_id):
        try:
            await bot.send_message(CHANNEL_USERNAME, text)
            await bot.send_message(user_id, "🎉 Your scheduled post has been published!")
            if user_id in pending_posts:
                del pending_posts[user_id]
        except Exception as e:
            logging.error(f"Error sending scheduled post: {e}")
            await bot.send_message(ADMIN_ID, f"❌ Error publishing scheduled post for user {user_id}: {str(e)}")

    scheduler.add_job(
        send_to_channel, 
        "date", 
        run_date=dt, 
        args=[text, user_id],
        id=f"post_{user_id}_{int(dt.timestamp())}"
    )
    
    await bot.send_message(user_id, f"📅 Your post has been scheduled for {time_str}.")
    await message.reply(f"✅ Post scheduled for {time_str}.")
    await state.clear()

@dp.message(Command("start"))
async def start_command(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.reply("👋 Welcome Admin! Forward messages to approve/reject submissions.")
    else:
        await message.reply("👋 Welcome! Send me your content and I'll forward it for admin review.")