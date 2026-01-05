import re
import asyncio
import base64
from pyrogram import Client, enums
from config import API_ID, API_HASH, BOT_TOKEN, WORKER_BOT_TOKENS, CACHE_SIZE, CACHE_DIR
from asyncio import Queue
from utility import Cache

cache = Cache(CACHE_DIR, CACHE_SIZE)

worker_queue = Queue()

class Bot(Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.copy_lock = asyncio.Lock()

    def sanitize_query(self, query):
        """Sanitizes and normalizes a search query for consistent matching of 'and' and '&'."""
        query = query.strip().lower()
        query = re.sub(r"\s*&\s*", " and ", query)
        query = re.sub(r"[:',]", "", query)
        query = re.sub(r"[.\s_\-\(\)\[\]!]+", " ", query).strip()
        return query

    def remove_surrogates(self, text):
        return ''.join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))

    def encode_file_link(self, channel_id, message_id):
        raw = f"{channel_id}_{message_id}".encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

# Initialize main bot
bot = Bot(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML
)

# Initialize worker bots
worker_bots = [
    Client(f"worker_{i}", api_id=API_ID, api_hash=API_HASH, bot_token=token, sleep_threshold=60, no_updates=True)
    for i, token in enumerate(WORKER_BOT_TOKENS)
]

async def get_worker_bot():
    """Gets a worker from the queue."""
    return await worker_queue.get()

async def release_worker(worker):
    """Releases a worker back to the queue."""
    await worker_queue.put(worker)
