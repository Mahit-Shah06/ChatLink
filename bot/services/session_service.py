import json
import os
from datetime import datetime

SESSIONS_FILE = "storage/sessions.json"


class SessionService:
    def __init__(self):
        os.makedirs("storage", exist_ok=True)
        if not os.path.exists(SESSIONS_FILE):
            with open(SESSIONS_FILE, "w") as f:
                json.dump({}, f)

    def load(self):
        with open(SESSIONS_FILE, "r") as f:
            return json.load(f)

    def save(self, data):
        with open(SESSIONS_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def is_owner(self, user_id: int, channel_id: int) -> bool:
        sessions = self.load()
        for uid, info in sessions.items():
            if info["channel_id"] == channel_id:
                return str(user_id) == uid
        return False

    def get_owner(self, channel_id: int):
        sessions = self.load()
        for uid, info in sessions.items():
            if info["channel_id"] == channel_id:
                return uid
        return None

    def create(self, user_id: int, channel_id: int):
        sessions = self.load()
        now = datetime.now()

        sessions[str(user_id)] = {
            "channel_id": channel_id,
            "toc": now.strftime("%H:%M:%S"),
            "doc": now.strftime("%Y-%m-%d")
        }

        self.save(sessions)

    def delete(self, user_id: int):
        sessions = self.load()
        sessions.pop(str(user_id), None)
        self.save(sessions)
