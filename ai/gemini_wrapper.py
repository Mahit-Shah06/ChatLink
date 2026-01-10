import google.generativeai as genai

class GeminiAI:
    def response(self, messages: list, api_key: str) -> str:
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel("gemini-pro")

        prompt = []
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            prompt.append(f"{role}: {msg['content']}")

        result = model.generate_content("\n".join(prompt))
        return result.text
