
import re
import base64
import logging
from config import *

# =========================
# Constants & Globals
# =========================

AUTO_DELETE_SECONDS = 2 * 60

logger = logging.getLogger(__name__)


import diskcache as dc
import asyncio

class Cache:
    def __init__(self, directory, size_limit):
        self.cache = dc.Cache(directory, size_limit=size_limit, eviction_policy='least-recently-used')

    async def get(self, key):
        return await asyncio.to_thread(self.cache.get, key)

    async def put(self, key, value):
        await asyncio.to_thread(self.cache.set, key, value)

    def __contains__(self, key):
        # Note: This is a blocking operation. Use with caution in async code.
        # The primary get/put operations are now async.
        return key in self.cache

# =========================
# Link & URL Utilities
# =========================

def generate_telegram_link(bot_username, channel_id, message_id):
    """Generate a base64-encoded Telegram deep link for a file."""
    raw = f"{channel_id}_{message_id}".encode()
    b64 = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return f"https://telegram.dog/{bot_username}?start=file_{b64}" 

def generate_c_link(channel_id, message_id):
    # channel_id must be like -1001234567890
    return f"https://t.me/c/{str(channel_id)[4:]}/{message_id}"

def extract_channel_and_msg_id(link):
    # Only support t.me/c/(-?\d+)/(\d+)
    match = re.search(r"t\.me/c/(-?\d+)/(\d+)", link)
    if match:
        channel_id = int("-100" + match.group(1)) if not match.group(1).startswith("-100") else int(match.group(1))
        msg_id = int(match.group(2))
        return channel_id, msg_id
    raise ValueError("Invalid Telegram message link format. Only /c/ links are supported.")
    

def human_readable_size(size):
    for unit in ['B','KB','MB','GB','TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"

def remove_extension(caption):
    try:
        # Remove the extension and everything after it
        cleaned_caption = re.sub(r'\.(mkv|mp4|webm).*$', '', caption, flags=re.IGNORECASE)
        return cleaned_caption
    except Exception as e:
        logger.error(e)
        return None
    
def remove_unwanted(caption):
    try:
        # Match and keep everything up to and including the extension
        match = re.match(r'^(.*?\.(mkv|mp4|webm))', caption, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return caption  # Return original if no match
    except Exception as e:
        logger.error(e)
        return None
        
