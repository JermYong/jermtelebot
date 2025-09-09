import asyncio
import logging
import sys
import threading
import os
from TeleBot import dp, bot, scheduler

from fastapi import FastAPI
import uvicorn

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

@app.get("/")
async def root():
    return {"status": "alive"}

def run_webserver():
    port = int(os.environ.get("PORT", 10000))  # Render injects PORT
    uvicorn.run(app, host="0.0.0.0", port=port)

async def main():
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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)