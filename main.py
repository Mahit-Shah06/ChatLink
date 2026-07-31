import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("discord").setLevel(logging.WARNING)
log = logging.getLogger("chatlink")


# Explicit rather than Intents.all(). presences is the expensive one — it makes
# Discord stream every status change for every member in every guild, and nothing
# in this bot reads presence. members and message_content are genuinely needed
# (join/leave logging and reading message text respectively) and must also be
# enabled in the Developer Portal.
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.voice_states = True
INTENTS.guilds = True
INTENTS.reactions = True

EXTENSIONS = [
    "bot.events.on_message",
    "bot.events.on_learning",
    "bot.events.on_member",
    "bot.events.on_voice",
    "bot.events.on_command",
    "bot.events.on_error",
    "bot.logging.logger",
    "bot.commands.help",
    "bot.commands.admin_commands",
    "bot.commands.logging_commands",
    "bot.commands.learning_setup",
    "bot.commands.secret_santa",
    "bot.commands.caller",
    "bot.commands.retard",
]


class ChatLink(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=INTENTS,
            help_command=None,
            # 10k cached messages is ~50-100MB of RAM for a feature only
            # on_message_delete uses. 1k still covers any realistic delete window.
            max_messages=1000,
        )

    async def setup_hook(self):
        loaded, failed = 0, 0
        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                loaded += 1
            except Exception as exc:
                failed += 1
                log.error("failed to load %s: %s", ext, exc)

        log.info("extensions loaded: %d ok, %d failed", loaded, failed)

        try:
            synced = await self.tree.sync()
            log.info("slash commands synced (%d)", len(synced))
        except Exception as exc:
            log.error("slash sync failed: %s", exc)


bot = ChatLink()


@bot.event
async def on_ready():
    log.info("logged in as %s (id %s)", bot.user, bot.user.id)
    log.info("serving %d guild(s)", len(bot.guilds))


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set. Add it to .env before starting.")
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("shutting down")
