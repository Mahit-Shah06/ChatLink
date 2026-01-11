import discord
from enum import Enum

LOG_CATEGORY_NAME = "logs"

class LogType(Enum):
    MESSAGE = "messages"
    VOICE = "voice"
    COMMAND = "commands"
    MEMBER = "members"
    SYSTEM = "system"

class Logger:
    def __init__(self, bot: discord.Client):
        self.bot = bot

    async def setup_guild(self, guild: discord.Guild):
        # Create logs category
        category = discord.utils.get(guild.categories, name=LOG_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(LOG_CATEGORY_NAME)

        # Create log channels
        for log in LogType:
            if not discord.utils.get(category.text_channels, name=log.value):
                await guild.create_text_channel(
                    log.value,
                    category=category
                )

    async def log(self, guild: discord.Guild, log_type: LogType, title: str, description: str):
        category = discord.utils.get(guild.categories, name=LOG_CATEGORY_NAME)
        if not category:
            return

        channel = discord.utils.get(category.text_channels, name=log_type.value)
        if not channel:
            return

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Server: {guild.name}")

        await channel.send(embed=embed)
