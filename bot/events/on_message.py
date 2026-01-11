import discord, json, os
from bot.services.ai_chat_service import AIChatService

ai = AIChatService()

async def handle_on_message(bot, message: discord.Message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if message.content.startswith("!"):
        return

    if not message.channel.category or message.channel.category.name != "ChatGPT":
        return

    if not os.path.exists("storage/sessions.json"):
        return

    with open("storage/sessions.json") as f:
        sessions = json.load(f)

    owner = next((int(uid) for uid, v in sessions.items()
                  if v["channel_id"] == message.channel.id), None)

    if not owner:
        return

    reply = ai.handle_message(message.channel.id, owner, message.content)
    await message.channel.send(reply)
