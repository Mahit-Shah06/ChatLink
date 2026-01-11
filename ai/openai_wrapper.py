from openai import OpenAI
import google.generativeai as genai

class AIWrapper:
    def openai_chat(self, messages, api_key):
        client = OpenAI(api_key=api_key)
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        return res.choices[0].message.content

    def gemini_chat(self, messages, api_key):
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        text = "\n".join(m["content"] for m in messages if m["role"] == "user")
        return model.generate_content(text).text