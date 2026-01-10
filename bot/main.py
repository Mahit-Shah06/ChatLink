import discord
import os
from discord.ext import commands
from dotenv import load_dotenv

from bot.events.on_message import handle_on_message

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


@bot.event
async def on_message(message):
    await handle_on_message(bot, message)

INITIAL_EXTENSIONS = [
    "bot.commands.secret_santa",
    # later:
    # "bot.commands.session",
    # "bot.commands.api",
    # "bot.commands.admin",
]

for ext in INITIAL_EXTENSIONS:
    try:
        bot.load_extension(ext)
        print(f"📦 Loaded {ext}")
    except Exception as e:
        print(f"❌ Failed to load {ext}: {e}")


bot.run(os.getenv("DISCORD_TOKEN"))
