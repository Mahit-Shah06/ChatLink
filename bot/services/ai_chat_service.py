from ai.openai_wrapper import OpenAIWrapper
from bot.services.api_key_service import APIKeyService


class AIChatService:
    def __init__(self):
        self.key_service = APIKeyService()
        self.ai = OpenAIWrapper()

    def chat(self, user_id: int, message: str):
        api_key = self.key_service.get_key(user_id)
        if not api_key:
            return "❌ No API key found. Use `!setkey <your_key>` first."

        return self.ai.ask(api_key, message)
