import discord
from bot.logging.log_types import LogType
from bot.logging.embed_factory import build_embed
from bot.logging.channel_resolver import resolve_channel
from bot.core.state_manager import state


class Logger:
    def __init__(self, bot):
        self.bot = bot

    async def process_event(self, guild: discord.Guild, log_type: LogType, key: int):
        print(f"[DEBUG] Logger received signal for: {log_type.name} | Guild: {guild.name}")

        if not state.is_enabled(guild.id, log_type):
            print(f"[DEBUG] {log_type.name} is DISABLED for guild {guild.id}")
            return

        event_state = state.get_state(log_type, key)
        if not event_state:
            print(f"[DEBUG] No state data found for key: {key}")
            return

        channel_id = state.get_log_channel(guild.id, log_type)
        if channel_id:
            channel = guild.get_channel(channel_id)
        else:
            channel_name = resolve_channel(log_type)
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            print(f"[DEBUG] Fallback search by name '{channel_name}': {channel}")

        if channel:
            try:
                embed = build_embed(
                    title=event_state.data["title"],
                    description=event_state.data["description"],
                    log_type=log_type,
                    tmstmp=event_state.timestamp
                )
                await channel.send(embed=embed)
                print(f"[SUCCESS] Sent {log_type.name} embed to #{channel.name} in {guild.name}")
            except Exception as e:
                print(f"[ERROR] Failed to send embed: {e}")
        else:
            print(f"[DEBUG] No log channel found for {log_type.name} in {guild.name} ({guild.id})")


async def setup(bot):
    bot.logger_instance = Logger(bot)