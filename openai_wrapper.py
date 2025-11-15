from openai import OpenAI

class AI:
    def response(self, message_list, api_key):
        client = OpenAI(api_key = api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages = message_list
        )
        return response.choices[0].message["content"]
