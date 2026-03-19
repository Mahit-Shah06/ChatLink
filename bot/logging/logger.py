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
        print(f"[DEBUG] Logger received signal for: {log_type.name}") # DEBUG 1
        
        if not self.toggles.get(log_type, True):
            print(f"[DEBUG] {log_type.name} is DISABLED in toggles.") # DEBUG 2
            return

        event_state = state.get_state(log_type, key)
        if not event_state:
            print(f"[DEBUG] No state data found in memory for key: {key}") # DEBUG 3
            return

        channel_id = state.log_channels.get(log_type)
        print(f"[DEBUG] Resolved Channel ID from state: {channel_id}") # DEBUG 4
        
        if not channel_id:
            # Fallback to name if ID is missing (common after bot restart)
            channel_name = resolve_channel(log_type)
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            print(f"[DEBUG] ID missing, searching by name '{channel_name}': {channel}") # DEBUG 5
        else:
            channel = guild.get_channel(channel_id)

        if channel:
            try:
                embed = build_embed(
                    title=event_state.data['title'],
                    description=event_state.data['description'],
                    log_type=log_type,
                    tmstmp=event_state.timestamp
                )
                await channel.send(embed=embed)
                print(f"[SUCCESS] Sent {log_type.name} embed to #{channel.name}") # DEBUG 6
            except Exception as e:
                print(f"[ERROR] Failed to send embed: {e}") # DEBUG 7
        else:
            print(f"[DEBUG] Could not find channel object in guild for {log_type.name}") # DEBUG 8

async def setup(bot):
    bot.logger_instance = Logger(bot)