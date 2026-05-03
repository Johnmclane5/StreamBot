
import os
import sys
import logging
import subprocess
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatPrivileges
from pyrogram.errors import RPCError, BotMethodInvalid
from config import OWNER_ID
from app import bot, worker_bots
from utility import auto_delete_message

@bot.on_message(filters.command("add_workers") & filters.private & filters.user(OWNER_ID))
async def add_workers_command(client: Client, message: Message):
    # Provide buttons for each worker bot
    buttons = []
    for i, worker in enumerate(worker_bots):
        worker_username = worker.username
        if not worker_username:
            # If worker username is not yet available, we can't create the link properly
            # We could try to fetch it, but let's assume it should be there after start
            continue
        
        link = f"https://t.me/{worker_username}?startchannel=true&admin=post_messages+invite_users"
        buttons.append([InlineKeyboardButton(f"Add Worker {i+1} (@{worker_username})", url=link)])
    
    if not buttons:
        await message.reply_text("No worker bots configured or they are not started yet.")
        return

    await message.reply_text(
        "<b>Add Workers to Channel:</b>\n\n"
        "Click the buttons below to add each worker bot to your channel. "
        "They need 'Post Messages' and 'Invite Users' permissions.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

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
