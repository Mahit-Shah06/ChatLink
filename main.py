import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

from bot.services.productivity_service import ProductivityService

load_dotenv()

INTENTS = discord.Intents.all()


class ChatLink(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=INTENTS,
            help_command=None,
            max_messages=10000
        )
        self.productivity_service = ProductivityService()

    async def setup_hook(self):
        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                print(f"✅ Loaded {ext}")
            except Exception as e:
                print(f"❌ Failed to load {ext}: {e}")

        await self.tree.sync()
        print("✅ Slash commands synced")


bot = ChatLink()

EXTENSIONS = [
    "bot.events.on_message",
    "bot.events.on_member",
    "bot.events.on_voice",
    "bot.events.on_command",
    "bot.events.on_error",
    "bot.logging.logger",
    "bot.events.on_productivity",
    "bot.commands.productivity",
    "bot.core.productivity_tasks",
    "bot.commands.help",
    "bot.commands.admin_commands",
    "bot.commands.secret_santa",
    "bot.commands.caller",
    "bot.commands.retard",
]


@bot.event
async def on_ready():
    print("=" * 50)
    print(f"🤖 Logged in as: {bot.user}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print(f"📡 Servers: {len(bot.guilds)}")
    print("=" * 50)


async def main():
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())