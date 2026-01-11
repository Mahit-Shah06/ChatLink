import discord
from bot.logging.log_types import LogType
from bot.logging.channel_resolver import resolve_channel
from bot.logging.embed_factory import build_embed

LOG_CATEGORY_NAME = "logs"

class Logger:
    def __init__(self, bot: discord.Client):
        self.bot = bot

    async def _get_log_channel(self, guild: discord.Guild, log_type: LogType):
        category = discord.utils.get(guild.categories, name=LOG_CATEGORY_NAME)
        if not category:
            return None

        channel_name = resolve_channel(log_type)
        return discord.utils.get(category.text_channels, name=channel_name)

    async def log(self, guild, log_type: LogType, title: str, description: str):
        channel = await self._get_log_channel(guild, log_type)
        if not channel:
            return

        embed = build_embed(title, description, log_type)
        await channel.send(embed=embed)
