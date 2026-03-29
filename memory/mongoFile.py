import os
import pymongo
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

MONGO_AVAILABLE = False
sync_db = None
async_db = None
db = None  # Kept for legacy imports

try:
    _test_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    _test_client.admin.command("ping")
    _test_client.close()

    _sync_client = pymongo.MongoClient(MONGO_URI)
    sync_db = _sync_client["chatlink"]

    _async_client = AsyncIOMotorClient(MONGO_URI)
    async_db = _async_client["chatlink"]

    db = async_db
    MONGO_AVAILABLE = True
    print("✅ MongoDB connected successfully")

except Exception as e:
    print(f"⚠️  MongoDB unavailable ({e})")
    print("     → Falling back to local JSON storage")
    MONGO_AVAILABLE = False


async def ping_db():
    if not MONGO_AVAILABLE:
        print("ℹ️  MongoDB is offline — using local storage")
        return
    try:
        await async_db.command("ping")
        print("✅ MongoDB ping successful")
    except Exception as e:
        print(f"❌ MongoDB ping failed: {e}")