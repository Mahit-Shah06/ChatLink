"""
MongoDB connection, with a local-first default.

The previous version opened a synchronous pymongo client at import time and
pinged it with a 3 second timeout. When Mongo was unreachable — which is the
normal case now that ChatLink runs locally — that was a guaranteed three second
stall on every single boot, before the bot had even started connecting to
Discord.

Now: if MONGO_URI is not set, Mongo is simply off and nothing is attempted. If
it is set, the probe runs with a short timeout. Either way the module-level
names other code imports (MONGO_AVAILABLE, async_db, sync_db, db) keep working
exactly as before.
"""

import logging
import os

logger = logging.getLogger("chatlink.mongo")

MONGO_URI = os.getenv("MONGO_URI", "").strip()
PROBE_TIMEOUT_MS = int(os.getenv("MONGO_PROBE_TIMEOUT_MS", "800"))

MONGO_AVAILABLE = False
sync_db = None
async_db = None
db = None  # kept for legacy imports


if not MONGO_URI:
    logger.info("MONGO_URI not set — using local JSON storage")
else:
    try:
        import pymongo
        from motor.motor_asyncio import AsyncIOMotorClient

        probe = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=PROBE_TIMEOUT_MS)
        probe.admin.command("ping")
        probe.close()

        _sync_client = pymongo.MongoClient(MONGO_URI)
        sync_db = _sync_client["chatlink"]

        _async_client = AsyncIOMotorClient(MONGO_URI)
        async_db = _async_client["chatlink"]

        db = async_db
        MONGO_AVAILABLE = True
        logger.info("MongoDB connected")

    except Exception as exc:
        logger.warning("MongoDB unavailable (%s) — falling back to local JSON storage", exc)
        MONGO_AVAILABLE = False


async def ping_db():
    if not MONGO_AVAILABLE:
        logger.info("MongoDB is offline — using local storage")
        return False
    try:
        await async_db.command("ping")
        return True
    except Exception as exc:
        logger.error("MongoDB ping failed: %s", exc)
        return False
