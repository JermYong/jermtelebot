import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import logging
from logger_utils import log_action

logging.basicConfig(level=logging.INFO)

# Secret files reading
def get_api_key(path="/etc/secrets/API_KEY"):
    with open(path, "r") as f:
        return f.read().strip()

def get_user_id(path="/etc/secrets/Telegram_ID"):
    with open(path, "r") as f:
        return int(f.read().strip())

def get_channel_username(path="/etc/secrets/CHANNEL_USERNAME"):
    with open(path, "r") as f:
        return f.read().strip()


API_TOKEN = get_api_key()
ADMIN_ID = get_user_id()
CHANNEL_USERNAME = get_channel_username()
CHANNEL_USERNAME = "@okchannel123123"

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()
pending_posts = {} 

class AdminStates(StatesGroup):
    waiting_for_schedule_time = State()
    waiting_for_reject_reason = State()

@dp.message(Command("start"))
async def start_command(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.reply("👋 Welcome Admin! Forward messages to approve/reject submissions.")
        log_action(message.from_user.id, "Admin /start", {})

    else:
        await message.reply("👋 Welcome! Send me your photo and caption to submit a post for admin approval.")
        log_action(message.from_user.id, "/start", {})

# User sends post with photo and optional text caption
@dp.message(lambda message: message.from_user.id != ADMIN_ID)
async def receive_submission(message: types.Message):
    if not message.photo:
        await message.reply("❌ Please send a photo with your post.")
        return
    if not message.caption:
        await message.reply("❌ Please send a caption with your post.")
        return
    
    if len(message.caption) > 970:
        await message.reply("❌ Caption is too long. Please send a caption shorter than 970 characters.")
        return
    
    user_id = message.from_user.id
    caption = message.caption or ""
    file_id = message.photo[-1].file_id  # best quality
    submission_id = message.message_id
    pending_posts[user_id] = {"submission_id":submission_id, 
                            "caption": caption, 
                            "file_id": file_id}
    log_action(user_id, f"@{message.from_user.username}, submission with {submission_id}", {"caption": caption + f"len:{len(caption)}", "file_id": file_id})
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Approve", callback_data=f"approve_{user_id}"),
            types.InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{user_id}")
        ]
    ])

    await bot.send_photo(
        ADMIN_ID,
        file_id,
        caption=f"New submission, ID: {submission_id} from {user_id} (@{message.from_user.username or 'no_username'}):\n\n{caption}",
        reply_markup=keyboard
    )
    await message.reply("✅ Submission received! Awaiting admin review.")

# Admin approves with /approve <user_id>
@dp.message(Command("approve"))
async def approve_command(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) >= 2 and parts[1].isdigit():
        print(parts)
        user_id = int(parts[1])
        if user_id not in pending_posts:
            await message.reply("❌ No pending submission for this user.")
            return
        await state.update_data(user_id=user_id)
        # await state.update_data(submission_id=submission_id)
        await state.set_state(AdminStates.waiting_for_schedule_time)
        await message.reply("📅 Please send schedule time ('YYYY-MM-DD HH:MM') or 'now' for immediate posting:")
    else:
        await message.reply("❌ Usage: /approve <user_id>")

# Admin rejects with /reject <user_id>, then waits for reason
@dp.message(Command("reject"))
async def reject_command(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) >= 2 and parts[1].isdigit():
        user_id = int(parts[1])
        if user_id not in pending_posts:
            await message.reply("❌ No pending submission for this user.")
            return
        await state.update_data(user_id=user_id)
        # await state.update_data(submission_id=submission_id)
        await state.set_state(AdminStates.waiting_for_reject_reason)
        await message.reply("❌ Send reject reason:")
    else:
        await message.reply("❌ Usage: /reject <user_id>")

# Handle reject reason text input by admin
@dp.message(AdminStates.waiting_for_reject_reason)
async def process_reject_reason(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    user_id = data.get("user_id")
    # submission_id = data.get("submission_id")
    reason = message.text.strip()

    if user_id in pending_posts:
        del pending_posts[user_id] #[submission_id]

    try:
        await bot.send_message(user_id, f"❌ Your submission was rejected.\nReason: {reason}")
        log_action(user_id, "rejected", {"reason": reason})

    except Exception:
        # user maybe blocked bot or other error
        pass

    await message.reply(f"✅ Rejection reason sent to user {user_id}.")
    await state.clear()

# Inline button approve handler
@dp.callback_query(lambda c: c.data.startswith('approve_'))
async def approve_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Unauthorized.", show_alert=True)
        return

    user_id = int(callback_query.data.split('_')[1])
    if user_id not in pending_posts:
        await callback_query.answer("No pending submission for this user.")
        return

    await state.update_data(user_id=user_id)
    await state.set_state(AdminStates.waiting_for_schedule_time)
    await callback_query.message.reply("📅 Please send schedule time ('YYYY-MM-DD HH:MM') or 'now' for immediate posting:")
    await callback_query.answer()

# Inline button reject handler
@dp.callback_query(lambda c: c.data.startswith('reject_'))
async def reject_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("Unauthorized.", show_alert=True)
        return

    user_id = int(callback_query.data.split('_')[1])
    if user_id not in pending_posts:
        await callback_query.answer("No pending submission for this user.")
        return
    
    data = await state.get_data()
    reason = data.get("reject_reason", "No reason provided")

    await state.update_data(user_id=user_id)
    await state.set_state(AdminStates.waiting_for_reject_reason)
    await callback_query.message.reply("❌ Send reject reason:")
    await callback_query.answer()

# Handle schedule time input by admin
@dp.message(AdminStates.waiting_for_schedule_time)
async def get_schedule_time(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    data = await state.get_data()
    user_id = data.get("user_id")
    if not user_id or user_id not in pending_posts:
        await message.reply("❌ No pending submission found.")
        await state.clear()
        return

    text = pending_posts[user_id].get("caption")
    file_id = pending_posts[user_id].get("file_id")
    time_str = message.text.strip()

    # Immediate posting
    if time_str.lower() == "now":
        log_action(ADMIN_ID, "approved submission", {"Message": "approved, now"})

        try:
            await bot.send_photo(CHANNEL_USERNAME, file_id, caption=text)
            log_action(123, f"bot schedule send to {CHANNEL_USERNAME}", {"Message": text, "file_id": file_id})
            await bot.send_message(user_id, "🎉 Your post has been published!")
            await message.reply("✅ Post published immediately.")
            del pending_posts[user_id]
        except Exception as e:
            await message.reply(f"❌ Error publishing post: {str(e)}")
        await state.clear()
        return

    # Scheduled posting
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        if dt <= datetime.now():
            await message.reply("❌ Scheduled time must be in the future.")
            return
    except ValueError:
        await message.reply("❌ Invalid date/time format. Use 'YYYY-MM-DD HH:MM' or 'now'.")
        return

    log_action(ADMIN_ID, "approved submission", {"Message": f"approved, scheduled for {time_str}"})

    # Define async job for scheduler: wrap coroutine call in a task
    def job_wrapper(caption, file_id, user_id):
        asyncio.create_task(send_scheduled_post(caption, file_id, user_id))

    async def send_scheduled_post(caption, file_id, user_id):
        try:
            await bot.send_photo(CHANNEL_USERNAME, file_id, caption=caption)
            log_action(ADMIN_ID, "Bot scheduled message", {"Message": f"Bot sending, {time_str}"})

            await bot.send_message(user_id, "🎉 Your scheduled post has been published!")
            if user_id in pending_posts:
                del pending_posts[user_id]
        except Exception as e:
            logging.error(f"Error sending scheduled post: {e}")
            await bot.send_message(ADMIN_ID, f"❌ Error publishing scheduled post for user {user_id}: {str(e)}")

    scheduler.add_job(
        send_scheduled_post,    # schedule the async function directly
        "date",
        run_date=dt,
        args=[text, file_id, user_id],
        id=f"post_{user_id}_{int(dt.timestamp())}"
    )

    await bot.send_message(user_id, f"📅 Your post has been scheduled for {time_str}.")
    await message.reply(f"✅ Post scheduled for {time_str}.")
    await state.clear()




# # Start scheduler and polling (put this in your main.py or entrypoint)

async def main():
    scheduler.start()
    await dp.start_polling()

# # if __name__ == "__main__":
# #     asyncio.run(main())
