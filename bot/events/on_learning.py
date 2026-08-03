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

#: Silent confirmation that a message was understood, and as what. Random gets
#: nothing — chit-chat shouldn't be decorated.
LABEL_REACTIONS = {
    "question": "\u2753",     # red question mark
    "note": "\U0001F4DD",     # memo
    "idea": "\U0001F4A1",     # light bulb
    "progress": "\U0001F4C8", # chart increasing
    "revision": "\U0001F501", # repeat
    "resource": "\U0001F517", # link
    "random": None,
}

#: A low-confidence auto label gets a thinking face instead, so you can spot
#: the ones worth checking with !learn fix without opening the dashboard.
UNSURE_REACTION = "\U0001F914"
LOW_CONFIDENCE = 0.5


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

    async def _capture(self, message: discord.Message, react: bool = True) -> bool:
        ctx, thread_id = self._context(message)
        if ctx is None:
            return False

        incoming = self._to_incoming(message, ctx, thread_id)
        processed = await asyncio.to_thread(self.engine.capture, incoming)
        if processed is None:
            return False

        label = processed.classification.label.value
        confidence = processed.classification.confidence
        topics = ", ".join(t.name for t in processed.topics[:3]) or "no topic"
        log.debug("captured %s (%.2f) [%s] in #%s",
                  label, confidence, topics, ctx.label)

        if react:
            emoji = (UNSURE_REACTION if confidence < LOW_CONFIDENCE
                     else LABEL_REACTIONS.get(label))
            if emoji:
                try:
                    await message.add_reaction(emoji)
                except discord.HTTPException:
                    pass  # missing permission or the message vanished

        return True

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
        # Don't re-react on an edit; the reaction from the original is still there.
        await self._capture(after, react=False)

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
