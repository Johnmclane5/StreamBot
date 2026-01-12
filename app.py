import re
import asyncio
import base64
import time
from pyrogram import Client, enums
from config import API_ID, API_HASH, BOT_TOKEN, WORKER_BOT_TOKENS, CACHE_SIZE, CACHE_DIR
from itertools import cycle
from utility import Cache

cache = Cache(CACHE_DIR, CACHE_SIZE)

class Bot(Client):
    def __init__(self, *args, **kwargs):
        self.id = kwargs.pop("id", None)
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
    Bot(f"worker_{i}", api_id=API_ID, api_hash=API_HASH, bot_token=token, sleep_threshold=60, no_updates=True, max_concurrent_transmissions=4, id=i)
    for i, token in enumerate(WORKER_BOT_TOKENS)
]

# Initialize the worker manager
worker_manager = None

class WorkerManager:
    def __init__(self, workers):
        self.workers = workers
        self.worker_tasks = {worker.id: 0 for worker in workers}
        self.cooldowns = {}
        self.COOLDOWN_PERIOD = 60  # in seconds

    def get_worker(self):
        now = time.time()
        available_workers = [
            w for w in self.workers 
            if w.id not in self.cooldowns or now - self.cooldowns[w.id] > self.COOLDOWN_PERIOD
        ]

        if not available_workers:
            return None

        # Find the worker with the minimum number of tasks
        worker = min(available_workers, key=lambda w: self.worker_tasks[w.id])
        self.worker_tasks[worker.id] += 1
        return worker

    def release_worker(self, worker_id):
        if self.worker_tasks[worker_id] > 0:
            self.worker_tasks[worker_id] -= 1

    def put_worker_on_cooldown(self, worker_id):
        self.cooldowns[worker_id] = time.time()

def get_worker_manager():
    global worker_manager
    if worker_manager is None:
        worker_manager = WorkerManager(worker_bots)
    return worker_manager