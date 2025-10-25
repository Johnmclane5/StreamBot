
import os
import logging
from dotenv import load_dotenv
from os import environ
from requests import get as rget

# Logger setup
LOG_FILE = "bot_log.txt"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("sharing_bot")
                
# Suppress Pyrogram logs except for errors
logging.getLogger("pyrogram").setLevel(logging.ERROR)

CONFIG_FILE_URL = environ.get('CONFIG_FILE_URL')
try:
    if len(CONFIG_FILE_URL) == 0:
        raise TypeError
    try:
        res = rget(CONFIG_FILE_URL)
        if res.status_code == 200:
            with open('config.env', 'wb+') as f:
                f.write(res.content)
        else:
            logger.error(f"Failed to download config.env {res.status_code}")
    except Exception as e:
        logger.info(f"CONFIG_FILE_URL: {e}")
except:
    pass

load_dotenv('config.env', override=True)

#TELEGRAM API
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
WORKER_BOT_TOKENS = [i.strip() for i in os.getenv('WORKER_BOT_TOKENS', '').split(',') if i.strip()]

OWNER_ID = int(os.getenv('OWNER_ID'))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))

MY_DOMAIN = os.getenv('MY_DOMAIN')

MONGO_URI = os.getenv("MONGO_URI")

# Caching configuration
CACHE_SIZE = 16 * 1024 * 1024 * 1024  # 16 GB
CHUNK_SIZE = 1024 * 1024  # 1 MB
CACHE_DIR = "cache"
