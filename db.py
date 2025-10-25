from pymongo import MongoClient
from config import MONGO_URI


# MongoDB setup
mongo = MongoClient(MONGO_URI)
db = mongo["sharing_bot"]
files_col = db["files"]


