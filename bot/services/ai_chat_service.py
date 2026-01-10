from ai.openai_wrapper import AI as OpenAI
from ai.gemini_wrapper import GeminiAI
from memory.cm_utils import Memory
from bot.services.api_key_service import APIKeyService

class AIChatService:
    def __init__(self):
        self.openai = OpenAI()
        self.gemini = GeminiAI()
        self.memory = Memory()
        self.key_service = APIKeyService()

    def handle_message(self, channel_id: int, user_id: int, content: str):
        keys = self.key_service.get_key(user_id)
        if not keys:
            raise RuntimeError("No API keys found")

        memory = self.memory.get_memory(channel_id)

        memory.append({
            "role": "user",
            "content": content
        })

        reply = None

        # Try OpenAI first
        try:
            reply = self.openai.response(memory, keys.get("openai"))
        except Exception as e:
            error_msg = str(e).lower()

            if "quota" in error_msg or "rate" in error_msg or "token" in error_msg:
                if not keys.get("gemini"):
                    raise RuntimeError("OpenAI quota hit and no Gemini key available")

                reply = self.gemini.response(memory, keys.get("gemini"))
            else:
                raise

        memory.append({
            "role": "assistant",
            "content": reply
        })

        self.memory.save_memory(channel_id, memory)
        return reply
