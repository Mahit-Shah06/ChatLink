from memory.mongoFile import db

collection = db["secret_santa"]

class SecretSantaMemory:
    def add_member(self, member):
        existing = collection.find_one(
            {"user_id": member.id}
        )
        if existing:
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
