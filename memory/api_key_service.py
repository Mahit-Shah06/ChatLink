from memory.mongoFile import db
from security.encrypting_utils import crypting

collection = db["api_keys"]

class APIKeyService:
    def __init__(self):
        self.crypto = crypting()

    def save_key(self, user_id: int, provider: str, key: str):
        encrypted = self.crypto.encrypting(key).decode()

        collection.update_one(
            {"user_id": user_id},
            {"$set": {f"keys.{provider}": encrypted}},
            upsert=True
        )

    def get_key(self, user_id: int, provider: str):
        doc = collection.find_one({"user_id": user_id})
        if not doc:
            return None

        enc = doc.get("keys", {}).get(provider)
        if not enc:
            return None

        return self.crypto.decrypting(enc.encode())
