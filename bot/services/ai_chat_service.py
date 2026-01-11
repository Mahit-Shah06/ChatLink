from ai.openai_wrapper import AIWrapper
from memory.cm_utils import Memory
from bot.services.api_key_service import APIKeyService

class AIChatService:
    def __init__(self):
        self.ai = AIWrapper()
        self.memory = Memory()
        self.keys = APIKeyService()

    def handle_message(self, channel_id, user_id, content):
        mem = self.memory.get_memory(channel_id)
        mem.append({"role": "user", "content": content})

        openai_key = self.keys.get_key(user_id, "openai")
        gemini_key = self.keys.get_key(user_id, "gemini")

        if openai_key:
            try:
                reply = self.ai.openai_chat(mem, openai_key)
            except Exception:
                if not gemini_key:
                    raise
                reply = self.ai.gemini_chat(mem, gemini_key)
        elif gemini_key:
            reply = self.ai.gemini_chat(mem, gemini_key)
        else:
            raise RuntimeError("No API keys found")

        mem.append({"role": "assistant", "content": reply})
        self.memory.save_memory(channel_id, mem)
        return reply
