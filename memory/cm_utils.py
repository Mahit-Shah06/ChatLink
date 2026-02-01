from memory.mongoFile import db

MAX_MSGS = 20
collection = db["memory"]

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
