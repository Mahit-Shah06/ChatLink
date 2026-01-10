import os
import json
import discord
from bot.services.ai_chat_service import AIChatService
from bot.services.rate_limit_service import RateLimitService

ai_service = AIChatService()
rate_limiter = RateLimitService()

async def handle_on_message(bot, message: discord.Message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if message.content.startswith("!"):
        return

    if not message.channel.category or message.channel.category.name != "ChatGPT":
        return

    if not rate_limiter.is_allowed(message.author.id, message.channel.id):
        return

    if not os.path.exists("storage/sessions.json"):
        return

    with open("storage/sessions.json", "r") as f:
        sessions = json.load(f)

    channel_id = message.channel.id
    owner_id = None

    for uid, info in sessions.items():
        if info["channel_id"] == channel_id:
            owner_id = int(uid)
            break

    if owner_id is None:
        return

    try:
        reply = ai_service.handle_message(
            channel_id=channel_id,
            user_id=owner_id,
            content=message.content
        )
    except Exception as e:
        await message.channel.send(f"⚠️ {e}", delete_after=5)
        return

    await message.channel.send(reply)
