import os
import json
import discord
from discord.ext import commands
from bot.services.ai_chat_service import AIChatService
from bot.services.rate_limit_service import RateLimitService

ai_service = AIChatService()
rate_limiter = RateLimitService()

async def handle_on_message(message: discord.Message):
    # 1. Basic checks
    if message.author.bot:
        return
    if message.content.startswith("!"):
        return
    if not message.channel.category or message.channel.category.name != "ChatGPT":
        return

    # 2. Rate Limit check
    if not rate_limiter.is_allowed(message.author.id, message.channel.id):
        return

    # 3. Session Owner check
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

    # 4. AI Response
    try:
        reply = ai_service.handle_message(
            channel_id=channel_id,
            user_id=owner_id,
            content=message.content
        )
        await message.channel.send(reply)
    except Exception as e:
        await message.channel.send(f"⚠️ {e}", delete_after=5)

async def setup(bot):
    # This connects the function to the bot's event system
    bot.add_listener(handle_on_message, 'on_message')