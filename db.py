from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI


# MongoDB setup
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["sharing_bot"]
files_col = db["files"]
