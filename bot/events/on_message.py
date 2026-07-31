import logging

from discord.ext import commands

from bot.core.state_manager import state
from bot.logging.log_types import LogType

log = logging.getLogger("chatlink.events.message")


class MessageListeners(commands.Cog):
    """Message logging.

    This runs on every message in every guild, so it is a hot path. The previous
    version built the embed payload and called into the logger unconditionally,
    with several print() calls per message — synchronous stdout writes on the
    event loop. Now the enabled check happens first and costs one dict lookup
    when logging is off, which is the common case.
    """

    def __init__(self, bot):
        self.bot = bot

    def _logging_on(self, message) -> bool:
        if message.guild is None:
            return False
        return state.is_enabled(message.guild.id, LogType.MESSAGE)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.content.startswith("!"):
            return
        if not self._logging_on(message):
            return

        state.update(LogType.MESSAGE, message.channel.id, {
            "title": "📥 Message Sent",
            "description": (
                f"**User:** {message.author.mention}\n"
                f"**Channel:** {message.channel.mention}\n"
                f"**Content:** {message.content or 'No text'}"
            ),
        })

        await self.bot.logger_instance.process_event(
            message.guild, LogType.MESSAGE, message.channel.id
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        if not self._logging_on(message):
            return

        content = message.content or "Content not found (message too old)"

        state.update(LogType.MESSAGE, message.channel.id, {
            "title": "🗑️ Message Deleted",
            "description": (
                f"**User:** {message.author.mention}\n"
                f"**Channel:** {message.channel.mention}\n"
                f"**Content:** {content}"
            ),
        })

        await self.bot.logger_instance.process_event(
            message.guild, LogType.MESSAGE, message.channel.id
        )


async def setup(bot):
    await bot.add_cog(MessageListeners(bot))
