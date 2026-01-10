import time

COOLDOWN_SECONDS = 4

class RateLimitService:
    def __init__(self):
        self._last_call = {}

    def is_allowed(self, user_id: int, channel_id: int) -> bool:
        key = (user_id, channel_id)
        now = time.time()

        last_time = self._last_call.get(key)
        if last_time and now - last_time < COOLDOWN_SECONDS:
            return False

        self._last_call[key] = now
        return True
