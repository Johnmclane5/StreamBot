
import asyncio
import uvicorn
import logging
import handlers

from app import bot, worker_bots
from db import files_col
from fast_api import api
from config import LOG_CHANNEL_ID

async def main():
    """
    Starts the bot and FastAPI server.
    """
    index_info = await files_col.index_information()
    if "file_name_text" not in index_info:
        await files_col.create_index([("file_name", "text")])
    try:
        await bot.start()
        logging.info("Main bot started.")
        for worker in worker_bots:
            await worker.start()
        logging.info("Multi client started.")
        await bot.send_message(LOG_CHANNEL_ID, "Bot started successfully!")
    except Exception as e:
        logging.error(f"Failed to start clients: {e}")
        await bot.send_message(LOG_CHANNEL_ID, f"Bot failed to start: {e}")

    # get the running event loop and schedule FastAPI server
    loop = asyncio.get_running_loop()
    loop.create_task(start_fastapi())

async def start_fastapi():
    """
    Starts the FastAPI server using Uvicorn.
    """
    try:
        config = uvicorn.Config(api, host="0.0.0.0", port=8000, loop="asyncio", log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()
    except KeyboardInterrupt:
        pass
        logging.info("FastAPI server stopped.")

if __name__ == "__main__":
    try:
        bot.loop.run_until_complete(main())
        bot.loop.run_forever()
    except KeyboardInterrupt:
        bot.stop()
        tasks = asyncio.all_tasks(loop=bot.loop)
        for task in tasks:
            task.cancel()
        bot.loop.stop()
        logging.info("Bot stopped.")