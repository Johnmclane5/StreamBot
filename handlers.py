
import os
import sys
import logging
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message
from config import OWNER_ID
from app import bot

@bot.on_message(filters.command("restart") & filters.user(OWNER_ID))
async def restart_command(client: Client, message: Message):
    await message.delete()
    try:
        subprocess.run([sys.executable, "update.py"], check=True)
    except subprocess.CalledProcessError as e:
        await message.reply_text(f"Update failed: {e}")
        return
    logging.info("Restarting bot...")
    os.execl(sys.executable, sys.executable, "-m", "bot")

@bot.on_message(filters.command("log") & filters.private & filters.user(OWNER_ID))
async def send_log_file(client, message: Message):
    log_file = "bot_log.txt"
    try:
        if not os.path.exists(log_file):
            await message.reply_text("Log file not found.")
            return
        await client.send_document(message.chat.id, log_file, caption="Here is the log file.")
    except Exception as e:
        pass
