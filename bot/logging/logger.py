import discord
from bot.logging.log_types import LogType
from bot.logging.embed_factory import build_embed
from bot.logging.channel_resolver import resolve_channel
from bot.core.state_manager import state

class Logger:
    def __init__(self, bot):
        self.bot = bot
        self.toggles = {lt: True for lt in LogType}

    async def process_event(self, guild: discord.Guild, log_type: LogType, key: int):
        # 1. Check if the admin toggled this log type OFF
        if not self.toggles.get(log_type, True):
            return

        # 2. Grab the specific event and its recorded timestamp from memory
        event_state = state.get_state(log_type, key)
        if not event_state:
            return

        # 3. Find the correct channel
        channel_name = resolve_channel(log_type)
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        
        if channel:
            # Build the embed with the timestamp recorded by the listener
            embed = build_embed(
                title=event_state.data['title'],
                description=event_state.data['description'],
                log_type=log_type,
                timestamp=event_state.timestamp
            )
            await channel.send(embed=embed)

async def setup(bot):
    bot.logger_instance = Logger(bot)