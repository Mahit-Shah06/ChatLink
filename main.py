import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

load_dotenv()

INTENTS = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=INTENTS,
    help_command=None
)

EXTENSIONS = [
#   "bot.events.on_message",
    "bot.logging.logger",
    "bot.commands.help",
    "bot.commands.admin_commands",
#   "bot.commands.session_commands",
#   "bot.commands.api_key_command",
#   "bot.commands.create_button",
#   "bot.commands.ai_chat_command",
    "bot.commands.secret_santa",
    "bot.commands.caller",
#   "bot.commands.extractor",
    "bot.commands.retard",
]

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"🤖 Logged in as: {bot.user}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print(f"📡 Servers: {len(bot.guilds)}")
    print("=" * 50)

async def load_extensions():
    for ext in EXTENSIONS:
        try:
            await bot.load_extension(ext)
            print(f"✅ Loaded {ext}")
        except Exception as e:
            print(f"❌ Failed to load {ext}: {e}")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())