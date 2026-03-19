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
            if not self.toggles.get(log_type, True):
                return

            event_state = state.get_state(log_type, key)
            if not event_state:
                return

            # Fetch ID from state manager instead of searching by name
            channel_id = state.log_channels.get(log_type)
            if not channel_id:
                return

            channel = guild.get_channel(channel_id)
            
            if channel:
                embed = build_embed(
                    title=event_state.data['title'],
                    description=event_state.data['description'],
                    log_type=log_type,
                    tmstmp=event_state.timestamp # Matches your embed_factory parameter name
                )
                await channel.send(embed=embed)

async def setup(bot):
    bot.logger_instance = Logger(bot)