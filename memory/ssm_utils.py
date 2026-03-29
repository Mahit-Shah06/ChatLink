from memory.mongoFile import MONGO_AVAILABLE, sync_db
from memory.local_store import local_db

if MONGO_AVAILABLE:
    collection = sync_db["secret_santa"]
else:
    collection = local_db["secret_santa"]


class SecretSantaMemory:
    def add_member(self, member):
        if collection.find_one({"user_id": member.id}):
            return False
        collection.insert_one({
            "user_id": member.id,
            "name": member.display_name
        })
        return True

    def get_entries(self):
        return [
            (doc["user_id"], doc["name"])
            for doc in collection.find()
        ]

    def clear(self):
        collection.delete_many({})