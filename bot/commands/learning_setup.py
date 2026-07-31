"""
Setup and inspection commands for the Learning Engine.

These are all read or configure operations. None of them start, stop or
otherwise gate capture — capture is always on for resolved channels, which is
the whole premise of the thing.

    !learn            what's being captured, and how much
    !learn setup      build categories and channels from data/syllabus.json
    !learn channels   full resolution table, including how each was resolved
    !learn recent     the last few captured messages
    !learn find <q>   full text search over everything captured
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from learning import get_engine
from learning.models import ChannelContext
from learning.syllabus import load_syllabus

log = logging.getLogger("chatlink.learnsetup")


class LearningSetup(commands.Cog):
    """Learning engine setup and status."""

    def __init__(self, bot):
        self.bot = bot
        self.engine = get_engine()

    @commands.group(name="learn", invoke_without_command=True)
    async def learn(self, ctx):
        """Show what the learning engine is capturing."""
        stats = await asyncio.to_thread(self.engine.stats)
        s = stats["summary"]

        embed = discord.Embed(
            title="🧠 Learning Engine",
            description=(
                "Capture is passive — every message in a mapped channel is stored "
                "automatically. There is nothing to start or stop."
            ),
            color=0x5865F2 if s["messages"] else discord.Color.greyple(),
        )
        embed.add_field(
            name="Captured",
            value=(
                f"**{s['messages']}** messages\n"
                f"**{s['attachments']}** attachments\n"
                f"**{s['active_days']}** active day(s)"
            ),
            inline=True,
        )
        embed.add_field(
            name="Channels",
            value=(
                f"**{stats['mapped_channels']}** mapped\n"
                f"**{stats['syllabus_channels']}** in syllabus\n"
                f"**{s['channels']}** seen"
            ),
            inline=True,
        )

        if s["first_day"]:
            embed.add_field(
                name="Range", value=f"{s['first_day']} → {s['last_day']}", inline=False
            )

        top = [c for c in stats["channels"] if c["messages"]][:5]
        if top:
            embed.add_field(
                name="Busiest channels",
                value="\n".join(f"`{c['label']}` — {c['messages']}" for c in top),
                inline=False,
            )
        else:
            embed.add_field(
                name="Nothing captured yet",
                value="Run `!learn setup` to build your channels, then just post normally.",
                inline=False,
            )

        embed.set_footer(text="!learn channels · !learn recent · !learn find <text>")
        await ctx.send(embed=embed)

    # ------------------------------------------------------------- bootstrap
    @learn.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def learn_setup(self, ctx):
        """Create categories and channels from data/syllabus.json. Admin only."""
        syllabus = await asyncio.to_thread(load_syllabus)
        if not syllabus.channel_count:
            return await ctx.send(
                "❌ No syllabus found. Copy `data/syllabus.example.json` to "
                "`data/syllabus.json`, edit it, then run this again."
            )

        progress = await ctx.send(
            f"Building {syllabus.channel_count} channel(s) across "
            f"{len(syllabus.categories)} category(ies)…"
        )

        created_categories, created_channels, existing = [], [], 0
        guild = ctx.guild

        try:
            for category_name, entries in syllabus.categories.items():
                category = discord.utils.get(guild.categories, name=category_name)
                if category is None:
                    category = await guild.create_category(category_name)
                    created_categories.append(category_name)

                for entry in entries:
                    channel = discord.utils.get(
                        guild.text_channels, name=entry.channel, category=category
                    )
                    if channel is None:
                        channel = await guild.create_text_channel(
                            entry.channel, category=category, topic=entry.name
                        )
                        created_channels.append(entry.channel)
                    else:
                        existing += 1

                    self.engine.channels.register(
                        ChannelContext(
                            external_id=str(channel.id),
                            label=entry.channel,
                            category=category_name,
                            context_kind=entry.context_kind,
                            context_value=entry.context_value,
                            subject_key=entry.key,
                            enabled=True,
                            origin="syllabus",
                        ),
                        persist=False,
                    )

            await asyncio.to_thread(self.engine.channels.save)

        except discord.Forbidden:
            return await progress.edit(
                content="❌ I need **Manage Channels** to do that."
            )
        except Exception as exc:
            log.exception("learn setup failed")
            return await progress.edit(content=f"❌ Setup failed: {exc}")

        embed = discord.Embed(title="✅ Learning channels ready", color=discord.Color.green())
        if created_categories:
            embed.add_field(
                name="Categories created",
                value="\n".join(created_categories), inline=False,
            )
        if created_channels:
            shown = created_channels[:15]
            more = len(created_channels) - len(shown)
            embed.add_field(
                name=f"Channels created ({len(created_channels)})",
                value=", ".join(f"`{c}`" for c in shown) + (f" +{more} more" if more else ""),
                inline=False,
            )
        if existing:
            embed.add_field(name="Already existed", value=f"{existing} channel(s)", inline=False)

        embed.add_field(
            name="What happens now",
            value=(
                "Every message you post in these channels is captured automatically. "
                "Reference channels are created but never captured."
            ),
            inline=False,
        )
        embed.set_footer(text=f"{len(self.engine.channels.all())} channels mapped")
        await progress.edit(content=None, embed=embed)

    # ------------------------------------------------------------ inspection
    @learn.command(name="channels")
    async def learn_channels(self, ctx):
        """Show every mapped channel and how it was resolved."""
        mapped = self.engine.channels.all()
        if not mapped:
            return await ctx.send(
                "No channels mapped yet. Run `!learn setup`, or just post in a "
                "channel whose name the engine can recognise."
            )

        groups: dict[str, list] = {}
        for c in sorted(mapped, key=lambda x: (x.context_value, x.label)):
            key = c.context_value or c.context_kind
            groups.setdefault(key, []).append(c)

        embed = discord.Embed(title="📚 Mapped channels", color=0x5865F2)
        for group, channels in groups.items():
            lines = []
            for c in channels:
                mark = "📕" if not c.captured else ("🔵" if c.origin == "syllabus" else "⚪")
                subject = f" → `{c.subject_key}`" if c.subject_key else ""
                lines.append(f"{mark} `{c.label}`{subject}")
            embed.add_field(name=group, value="\n".join(lines[:12]), inline=False)

        embed.set_footer(text="🔵 from syllabus · ⚪ inferred · 📕 reference, not captured")
        await ctx.send(embed=embed)

    @learn.command(name="recent")
    async def learn_recent(self, ctx, count: int = 10):
        """Show the most recently captured messages."""
        rows = await asyncio.to_thread(self.engine.repo.recent, max(1, min(count, 20)))
        if not rows:
            return await ctx.send("Nothing captured yet.")

        lines = []
        for r in rows:
            text = (r["content"] or "").replace("\n", " ")
            if len(text) > 70:
                text = text[:69] + "…"
            attach = f" 📎{r['attachment_count']}" if r["attachment_count"] else ""
            lines.append(f"`{r['local_date']} {r['local_hour']:02d}h` **{r['channel_label']}**{attach}\n{text or '*(attachment only)*'}")

        embed = discord.Embed(
            title=f"🕑 Last {len(rows)} captured",
            description="\n\n".join(lines),
            color=0x5865F2,
        )
        await ctx.send(embed=embed)

    @learn.command(name="find")
    async def learn_find(self, ctx, *, query: str):
        """Search everything captured so far."""
        try:
            rows = await asyncio.to_thread(self.engine.repo.search, query, 10)
        except Exception:
            return await ctx.send("Couldn't parse that search. Try plain words.")

        if not rows:
            return await ctx.send(f"Nothing found for **{query}**.")

        lines = []
        for r in rows:
            text = (r["content"] or "").replace("\n", " ")
            if len(text) > 80:
                text = text[:79] + "…"
            lines.append(f"`{r['local_date']}` **{r['channel_label'] or '?'}** — {text}")

        embed = discord.Embed(
            title=f"🔍 {len(rows)} result(s) for “{query}”",
            description="\n".join(lines),
            color=0x5865F2,
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(LearningSetup(bot))
