
import os
import sys
import logging
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message
from config import OWNER_ID
from app import bot
from utility import auto_delete_message

@bot.on_message(filters.command('restart') & filters.private & filters.user(OWNER_ID))
async def restart(client, message):
    await message.delete()
    # 🔄 Restart logic
    os.system("python3 update.py")
    os.execl(sys.executable, sys.executable, "bot.py")

@bot.on_message(filters.command("log") & filters.private & filters.user(OWNER_ID))
async def send_log_file(client, message: Message):
    log_file = "bot_log.txt"
    try:
        if not os.path.exists(log_file):
            await message.reply_text("Log file not found.")
            return
        reply = await client.send_document(message.chat.id, log_file, caption="Here is the log file.")
        bot.loop.create_task(auto_delete_message(message, reply))
    except Exception as e:
        pass
