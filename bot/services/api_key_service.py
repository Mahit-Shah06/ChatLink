import json
import os
from security.encrypting_utils import crypting

APIKEY_FILE = "storage/apikeys.json"

class APIKeyService:
    def __init__(self):
        self.crypto = crypting()
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists("storage"):
            os.makedirs("storage")

        if not os.path.exists(APIKEY_FILE):
            with open(APIKEY_FILE, "w") as f:
                json.dump({}, f)

    def save_key(self, user_id: int, raw_key: str):
        encrypted = self.crypto.encrypting(raw_key)

        with open(APIKEY_FILE, "r") as f:
            data = json.load(f)

        data[str(user_id)] = encrypted.decode()

        with open(APIKEY_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def get_key(self, user_id: int):
        if not os.path.exists(APIKEY_FILE):
            return None

        with open(APIKEY_FILE, "r") as f:
            data = json.load(f)

        enc = data.get(str(user_id))
        if not enc:
            return None

        return self.crypto.decrypting(enc.encode())
