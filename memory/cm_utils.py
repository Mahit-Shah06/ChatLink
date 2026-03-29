from memory.mongoFile import MONGO_AVAILABLE, sync_db
from memory.local_store import local_db

MAX_MSGS = 20

if MONGO_AVAILABLE:
    collection = sync_db["memory"]
else:
    collection = local_db["memory"]


class Memory:
    def get_memory(self, channel_id: int):
        doc = collection.find_one({"channel_id": channel_id})
        return doc["messages"] if doc else []

    def save_memory(self, channel_id: int, messages: list):
        messages = messages[-MAX_MSGS:]
        collection.update_one(
            {"channel_id": channel_id},
            {"$set": {"messages": messages}},
            upsert=True
        )

    def clear(self, channel_id: int):
        collection.delete_one({"channel_id": channel_id})