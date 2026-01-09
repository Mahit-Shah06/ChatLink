from ai.openai_wrapper import AI

class AIService:
    def __init__(self):
        self.ai = AI()

    def reply(self, memory: list, api_key: str) -> str:
        """
        memory: list of {role, content}
        api_key: decrypted OpenAI key
        """
        return self.ai.response(memory, api_key)
