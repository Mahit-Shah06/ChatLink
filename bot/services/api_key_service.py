import json, os
from security.encrypting_utils import crypting

FILE = "storage/apikeys.json"

class APIKeyService:
    def __init__(self):
        self.crypto = crypting()
        os.makedirs("storage", exist_ok=True)
        if not os.path.exists(FILE):
            with open(FILE, "w") as f:
                json.dump({}, f)

    def save_key(self, user_id, provider, key):
        with open(FILE) as f:
            data = json.load(f)

        data.setdefault(str(user_id), {})
        data[str(user_id)][provider] = self.crypto.encrypting(key).decode()

        with open(FILE, "w") as f:
            json.dump(data, f, indent=2)

    def get_key(self, user_id, provider):
        with open(FILE) as f:
            data = json.load(f)

        enc = data.get(str(user_id), {}).get(provider)
        if not enc:
            return None
        return self.crypto.decrypting(enc.encode())
