import logging

import discord

from bot.core.state_manager import state
from bot.logging.channel_resolver import resolve_channel
from bot.logging.embed_factory import build_embed
from bot.logging.log_types import LogType

log = logging.getLogger("chatlink.logger")


class Logger:
    """Dispatches log embeds to the configured channel.

    Every print() here used to run on every logged event, including the ones
    that were about to be discarded. They are now log.debug, so the output is
    off by default and can be turned on with LOG_LEVEL=DEBUG in .env without
    touching code.

    Channel resolution by name is also cached. The fallback path scanned
    guild.text_channels on every event, which is a linear search over the whole
    guild for a channel that never changes.
    """

    def __init__(self, bot):
        self.bot = bot
        self._channel_cache: dict[tuple[int, LogType], int] = {}

    def _resolve(self, guild: discord.Guild, log_type: LogType):
        channel_id = state.get_log_channel(guild.id, log_type)
        if channel_id:
            return guild.get_channel(channel_id)

        cache_key = (guild.id, log_type)
        cached = self._channel_cache.get(cache_key)
        if cached:
            channel = guild.get_channel(cached)
            if channel:
                return channel
            self._channel_cache.pop(cache_key, None)

        channel_name = resolve_channel(log_type)
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel:
            self._channel_cache[cache_key] = channel.id
        else:
            log.debug("no log channel named '%s' in %s", channel_name, guild.name)
        return channel

    def invalidate_cache(self, guild_id: int | None = None) -> None:
        """Call after !setup_logs creates or moves channels."""
        if guild_id is None:
            self._channel_cache.clear()
        else:
            for key in [k for k in self._channel_cache if k[0] == guild_id]:
                self._channel_cache.pop(key, None)

    async def process_event(self, guild: discord.Guild, log_type: LogType, key: int):
        if not state.is_enabled(guild.id, log_type):
            log.debug("%s disabled for guild %s", log_type.name, guild.id)
            return

        event_state = state.get_state(log_type, key)
        if not event_state:
            log.debug("no state data for key %s", key)
            return

        channel = self._resolve(guild, log_type)
        if not channel:
            return

        try:
            embed = build_embed(
                title=event_state.data["title"],
                description=event_state.data["description"],
                log_type=log_type,
                tmstmp=event_state.timestamp,
            )
            await channel.send(embed=embed)
            log.debug("sent %s to #%s in %s", log_type.name, channel.name, guild.name)
        except discord.Forbidden:
            log.warning("missing permission to post in #%s (%s)", channel.name, guild.name)
        except Exception as exc:
            log.error("failed to send %s embed: %s", log_type.name, exc)


async def setup(bot):
    bot.logger_instance = Logger(bot)
