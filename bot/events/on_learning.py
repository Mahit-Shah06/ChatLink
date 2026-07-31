"""
Discord adapter for the Learning Engine.

Deliberately thin. Its whole job is turning a discord.Message into an
IncomingMessage and handing it over. No SQL, no filtering logic, no
classification — and no commands at all.

That last part is the design. A channel is captured because of what it is, not
because someone remembered to type !start. If you ever find yourself wanting a
capture command, that's a signal the resolver failed to infer something, and
the fix belongs in syllabus.py.

Every engine call goes through asyncio.to_thread because SQLite writes block,
and this cog shares an event loop with the rest of ChatLink.
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from learning import Attachment, IncomingMessage, get_engine

log = logging.getLogger("chatlink.learning")


class LearningCapture(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.engine = get_engine()

    # ------------------------------------------------------------- helpers
    def _context(self, message: discord.Message):
        """Resolve a channel to its learning context, or None to ignore it.

        Threads inherit their parent channel's context — a thread in #dbms is
        still DBMS. Topic detection in phase 4 reads the text, not the location.
        """
        channel = message.channel
        thread_id = None

        if isinstance(channel, discord.Thread):
            thread_id = str(channel.id)
            channel = channel.parent
            if channel is None:
                return None, None

        category = channel.category.name if getattr(channel, "category", None) else ""
        ctx = self.engine.channels.resolve(channel.id, getattr(channel, "name", ""), category)
        return ctx, thread_id

    @staticmethod
    def _to_incoming(message: discord.Message, ctx, thread_id) -> IncomingMessage:
        return IncomingMessage(
            content=message.content or "",
            source="discord",
            external_id=str(message.id),
            author_id=str(message.author.id),
            author_name=message.author.display_name,
            thread_id=thread_id,
            reply_to=str(message.reference.message_id) if message.reference else None,
            channel=ctx,
            attachments=[
                Attachment(
                    filename=a.filename or "",
                    url=a.url or "",
                    content_type=a.content_type or "",
                    size_bytes=a.size or 0,
                )
                for a in message.attachments
            ],
            created_at=message.created_at,
            metadata={
                "guild_id": str(message.guild.id) if message.guild else None,
                "channel_name": getattr(message.channel, "name", ""),
                "jump_url": message.jump_url,
            },
        )

    async def _capture(self, message: discord.Message) -> bool:
        ctx, thread_id = self._context(message)
        if ctx is None:
            return False

        incoming = self._to_incoming(message, ctx, thread_id)
        message_id = await asyncio.to_thread(self.engine.capture, incoming)
        if message_id:
            log.debug("captured #%s message %s", ctx.label, message.id)
        return message_id is not None

    # -------------------------------------------------------------- events
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        await self._capture(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author.bot or not after.guild:
            return
        if before.content == after.content:
            return
        await self._capture(after)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        ctx, _ = self._context(message)
        if ctx is None:
            return
        await asyncio.to_thread(self.engine.forget, "discord", str(message.id))


async def setup(bot):
    await bot.add_cog(LearningCapture(bot))
