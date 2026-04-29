
import os
import sys
import logging
import subprocess
import uuid
import aiohttp
import imgbbpy
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from config import OWNER_ID, IMGBB_API_KEY, MY_DOMAIN
from app import bot
from utility import auto_delete_message, extract_channel_and_msg_id
from db import files_col

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

async def upload_to_imgbb(file_path):
    """
    Uploads a local image file to imgbb and returns the new URL data.
    """
    if not IMGBB_API_KEY:
        logging.error("IMGBB_API_KEY not found in environment variables.")
        return None

    client = None
    try:
        client = imgbbpy.AsyncClient(IMGBB_API_KEY)
        image = await client.upload(file=file_path, name=f"{uuid.uuid4()}")
        return {
            "url": image.url,
            "delete_url": getattr(image, "delete_url", None)
        }
    except Exception as e:
        logging.error(f"Error during imgbb upload process: {e}")
        return None
    finally:
        if client:
            await client.close()

async def generate_thumbnail(stream_url, output_path):
    """
    Generates a thumbnail from a stream URL using ffmpeg's thumbnail filter.
    """
    try:
        # Analyze 50 frames starting from the 5-second mark to pick the best representative frame
        process = await asyncio.create_subprocess_exec(
            'ffmpeg',
            '-ss', '00:00:05',
            '-i', stream_url,
            '-vf', 'thumbnail=50',
            '-vframes', '1',
            '-q:v', '2',
            output_path,
            '-y',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            logging.error(f"ffmpeg timeout for {stream_url}")
            return False

        if process.returncode != 0:
            # Log only the last line of stderr if available, or a generic error
            error_msg = stderr.decode(errors='replace').strip().split('\n')[-1] if stderr else "Unknown error"
            logging.error(f"ffmpeg error: {error_msg}")
            return False
        return True
    except Exception as e:
        logging.error(f"Error generating thumbnail: {e}")
        return False

@bot.on_message(filters.command("gen") & filters.private & filters.user(OWNER_ID))
async def gen_thumb_command(client, message: Message):
    if len(message.command) < 3:
        await message.reply_text("Usage: /gen_thumb <start_link> <end_link>")
        return

    start_link = message.command[1]
    end_link = message.command[2]

    try:
        start_channel_id, start_msg_id = extract_channel_and_msg_id(start_link)
        end_channel_id, end_msg_id = extract_channel_and_msg_id(end_link)
    except ValueError as e:
        await message.reply_text(str(e))
        return

    if start_channel_id != end_channel_id:
        await message.reply_text("Start and end links must be from the same channel.")
        return

    status_message = await message.reply_text("Starting thumbnail generation...")
    
    count = 0
    for msg_id in range(start_msg_id, end_msg_id + 1):
        file_doc = await files_col.find_one({"channel_id": start_channel_id, "message_id": msg_id})
        if not file_doc:
            continue
        
        # Check if it's likely a video by name or if we have media type info
        # The current db schema doesn't seem to store media type explicitly in all cases, 
        # but let's try to generate if it's not already there.
        if file_doc.get("poster_url"):
            continue

        file_link = bot.encode_file_link(start_channel_id, msg_id, OWNER_ID)
        stream_url = f"{MY_DOMAIN}/stream/{file_link}"
        temp_thumb = f"/tmp/{uuid.uuid4()}.jpg"

        try:
            if await generate_thumbnail(stream_url, temp_thumb):
                imgbb_data = await upload_to_imgbb(temp_thumb)
                if imgbb_data:
                    db_update = {"poster_url": imgbb_data["url"]}
                    if imgbb_data.get("delete_url"):
                        db_update["poster_delete_url"] = imgbb_data["delete_url"]
                    
                    await files_col.update_one({"_id": file_doc["_id"]}, {"$set": db_update})
                    count += 1
        finally:
            if os.path.exists(temp_thumb):
                os.remove(temp_thumb)
        
        if (msg_id - start_msg_id) % 10 == 0:
            await status_message.edit_text(f"Processing... Current ID: {msg_id}\nThumbnails generated: {count}")

    await status_message.edit_text(f"Thumbnail generation completed!\nTotal generated: {count}")
                    
