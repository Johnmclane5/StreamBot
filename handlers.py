
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

@bot.on_message(filters.command("add_workers") & filters.user(OWNER_ID))
async def add_workers_command(client: Client, message: Message):
    if message.chat.type == enums.ChatType.PRIVATE:
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
    else:
        # In a group or channel, try to add/promote them automatically
        status_msg = await message.reply_text("🔄 <b>Attempting to add and promote worker bots...</b>")
        
        # Check main bot permissions
        try:
            me_member = await client.get_chat_member(message.chat.id, "me")
            if not (me_member.privileges and me_member.privileges.can_promote_members and me_member.privileges.can_invite_users):
                await status_msg.edit_text(
                    "❌ <b>Error:</b> I don't have enough permissions to add or promote members.\n\n"
                    "<b>Required Permissions:</b>\n"
                    "- Add New Admins\n"
                    "- Invite Users\n\n"
                    "<b>One-Time Setup:</b>\n"
                    "Please add me as an admin with these permissions first, then run this command again.\n\n"
                    "Alternatively, add workers manually using buttons in private chat."
                )
                return
        except Exception as e:
            logging.error(f"Error checking bot permissions: {e}")
            await status_msg.edit_text(f"❌ <b>Error checking permissions:</b> {e}")
            return

        success_count = 0
        fail_count = 0
        error_details = []

        for worker in worker_bots:
            try:
                # Ensure peer is resolved
                try:
                    await client.get_users(worker.telegram_id)
                except Exception:
                    pass

                # Bots cannot use add_chat_members in channels, but promoting a non-member works if bot has invite rights
                await client.promote_chat_member(
                    chat_id=message.chat.id,
                    user_id=worker.telegram_id,
                    privileges=ChatPrivileges(
                        can_post_messages=True,
                        can_invite_users=True
                    )
                )
                success_count += 1
            except BotMethodInvalid:
                # Fallback if promote doesn't work for adding (e.g. in some group types)
                try:
                    await client.add_chat_members(message.chat.id, worker.telegram_id)
                    await client.promote_chat_member(
                        chat_id=message.chat.id,
                        user_id=worker.telegram_id,
                        privileges=ChatPrivileges(
                            can_post_messages=True,
                            can_invite_users=True
                        )
                    )
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    error_details.append(f"Worker {worker.worker_id}: {str(e)}")
            except RPCError as e:
                fail_count += 1
                error_details.append(f"Worker {worker.worker_id}: {e}")
            except Exception as e:
                fail_count += 1
                error_details.append(f"Worker {worker.worker_id}: {e}")
        
        summary = f"✅ <b>Successfully added/promoted {success_count} workers.</b>"
        if fail_count > 0:
            summary += f"\n❌ <b>Failed for {fail_count} workers.</b>"
            if error_details:
                summary += "\n\n<b>Errors:</b>\n" + "\n".join(error_details[:5]) # Show first 5 errors
        
        await status_msg.edit_text(summary)

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
