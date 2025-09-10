import asyncio
import logging
import sys
import os
from TeleBot import dp, bot, scheduler

from fastapi import FastAPI
from uvicorn import Config, Server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "alive"}

@app.head("/health")
async def health():
    return {"status": "alive"}

async def run_bot():
    """Main function to start the bot"""
    try:
        logger.info("Starting bot...")
        
        # Start the scheduler within the event loop
        logger.info("Starting scheduler...")
        scheduler.start()
        
        # Start polling
        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise
    finally:
        # Clean shutdown
        logger.info("Shutting down bot...")
        if scheduler.running:
            scheduler.shutdown()
        await bot.session.close()

async def main():
    # Start bot as background task
    bot_task = asyncio.create_task(run_bot())

    # Start FastAPI server
    port = int(os.environ.get("PORT", 10000))
    config = Config(app=app, host="0.0.0.0", port=port, log_level="info")
    server = Server(config)
    await server.serve()  # runs in same event loop

    # Wait for bot task to finish (never ends unless bot stops)
    await bot_task

# Start scheduler and polling (put this in your main.py or entrypoint)

async def main():
    scheduler.start()
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())