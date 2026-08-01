"""
Learning Engine commands.

Everything here reads or configures. Nothing starts or stops capture — capture
is always on for resolved channels, which is the premise of the whole thing.

    !learn              overview: what's captured, by label
    !learn setup        build channels from data/syllabus.json
    !learn channels     resolution table
    !learn weak         topics with open questions and no notes
    !learn stale        studied once, never revisited
    !learn topics       everything detected, ranked
    !learn today        what you did today
    !learn recent       last few captured messages
    !learn find <text>  full-text search
    !learn fix <id> <label>   correct a wrong label
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from learning import get_engine
from learning.models import ChannelContext, Label
from learning.syllabus import load_syllabus

log = logging.getLogger("chatlink.learn")

LABEL_EMOJI = {
    "question": "❓", "note": "📝", "idea": "💡", "progress": "📈",
    "revision": "🔁", "resource": "🔗", "random": "💬",
}


class LearningCommands(commands.Cog):
    """Learning engine setup and analytics."""

    def __init__(self, bot):
        self.bot = bot
        self.engine = get_engine()

    # ------------------------------------------------------------- overview
    @commands.group(name="learn", invoke_without_command=True)
    async def learn(self, ctx):
        """Show what the learning engine has captured."""
        stats = await asyncio.to_thread(self.engine.stats)
        s = stats["summary"]

        if not s["messages"]:
            embed = discord.Embed(
                title="🧠 Learning Engine",
                description=(
                    "Nothing captured yet.\n\n"
                    "Run `!learn setup` to build your channels, then just post "
                    "normally — doubts, notes, what you finished. There's nothing "
                    "to start or stop."
                ),
                color=discord.Color.greyple(),
            )
            return await ctx.send(embed=embed)

        labels = {r["label"]: r["count"] for r in stats["labels"] if r["label"]}
        breakdown = "\n".join(
            f"{LABEL_EMOJI.get(k, '·')} `{k:<9}` {v}"
            for k, v in sorted(labels.items(), key=lambda kv: -kv[1])
        ) or "*not classified yet*"

        embed = discord.Embed(title="🧠 Learning Engine", color=0x5865F2)
        embed.add_field(
            name="Captured",
            value=(f"**{s['messages']}** messages\n"
                   f"**{s['attachments']}** attachments\n"
                   f"**{stats['streak']}** day streak"),
            inline=True,
        )
        embed.add_field(name="By type", value=breakdown, inline=True)

        weak = await asyncio.to_thread(self.engine.repo.weak_topics, 2, 3)
        if weak:
            embed.add_field(
                name="⚠️ Needs attention",
                value="\n".join(
                    f"`{t['name']}` — {t['questions']} question(s), {t['notes']} note(s)"
                    for t in weak
                ),
                inline=False,
            )

        embed.set_footer(text=f"{stats['classifier']} · !learn weak · !learn topics")
        await ctx.send(embed=embed)

    # ------------------------------------------------------------ bootstrap
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
        created_cats, created_chans, existing = [], [], 0
        pinned, pin_failed = 0, []
        guild = ctx.guild

        try:
            for category_name, entries in syllabus.categories.items():
                category = discord.utils.get(guild.categories, name=category_name)
                if category is None:
                    category = await guild.create_category(category_name)
                    created_cats.append(category_name)

                for entry in entries:
                    # Find the channel anywhere in the guild, not just in this
                    # category — if you moved one by hand, we adopt it and move
                    # it back rather than creating a duplicate.
                    channel = discord.utils.get(guild.text_channels, name=entry.channel)
                    if channel is None:
                        channel = await guild.create_text_channel(
                            entry.channel, category=category, topic=entry.name)
                        created_chans.append(entry.channel)
                    else:
                        existing += 1
                        if channel.category != category:
                            await channel.edit(category=category)

                    self.engine.channels.register(
                        ChannelContext(
                            external_id=str(channel.id), label=entry.channel,
                            category=category_name, context_kind=entry.context_kind,
                            context_value=entry.context_value, subject_key=entry.key,
                            enabled=True, origin="syllabus"),
                        persist=False)

                    if entry.syllabus_text:
                        result = await self._pin_syllabus(channel, entry)
                        if result is True:
                            pinned += 1
                        elif result is False:
                            pin_failed.append(entry.channel)

            await asyncio.to_thread(self.engine.channels.save)

        except discord.Forbidden:
            return await progress.edit(
                content="❌ I need **Manage Channels** and **Manage Messages**.")
        except Exception as exc:
            log.exception("learn setup failed")
            return await progress.edit(content=f"❌ Setup failed: {exc}")

        embed = discord.Embed(title="✅ Learning channels ready", color=discord.Color.green())
        if created_cats:
            embed.add_field(name="Categories", value="\n".join(created_cats), inline=False)
        if created_chans:
            shown = created_chans[:15]
            more = len(created_chans) - len(shown)
            embed.add_field(
                name=f"Channels created ({len(created_chans)})",
                value=", ".join(f"`{c}`" for c in shown) + (f" +{more}" if more else ""),
                inline=False)
        if existing:
            embed.add_field(name="Already existed", value=f"{existing} channel(s)", inline=False)
        if pinned:
            embed.add_field(name="Syllabus pinned", value=f"{pinned} channel(s)", inline=False)
        if pin_failed:
            embed.add_field(
                name="⚠️ Could not pin",
                value=", ".join(f"`{c}`" for c in pin_failed) +
                      "\n(needs **Manage Messages** in those channels)",
                inline=False)
        embed.add_field(
            name="From now on",
            value="Post normally in those channels. Everything is captured, sorted "
                  "and linked to topics automatically. Reference channels are never captured.",
            inline=False)
        await progress.edit(content=None, embed=embed)

    async def _pin_syllabus(self, channel: discord.TextChannel, entry) -> bool | None:
        """Post the syllabus and pin it. Edits its own previous pin if there is one.

        Returns True if pinned, False on permission failure, None if nothing
        needed doing. Discord caps a message at 2000 characters, so long
        syllabi are split and only the first part is pinned.
        """
        header = f"📘 **{entry.name} — Syllabus**"
        body = f"{header}\n\n{entry.syllabus_text}"

        try:
            pins = await channel.pins()
        except discord.Forbidden:
            return False

        mine = [m for m in pins if m.author.id == self.bot.user.id
                and m.content.startswith("📘")]

        chunks = self._split(body)

        try:
            if mine:
                # Re-running setup shouldn't litter the channel with duplicates.
                if mine[0].content.strip() == chunks[0].strip():
                    return None
                await mine[0].edit(content=chunks[0])
                return True

            first = await channel.send(chunks[0])
            await first.pin()
            for extra in chunks[1:]:
                await channel.send(extra)
            return True
        except discord.Forbidden:
            return False
        except discord.HTTPException as exc:
            log.warning("pin failed in #%s: %s", channel.name, exc)
            return False

    @staticmethod
    def _split(text: str, limit: int = 1900) -> list[str]:
        """Split on blank lines so unit headings stay with their content."""
        if len(text) <= limit:
            return [text]
        chunks, current = [], ""
        for block in text.split("\n\n"):
            if len(current) + len(block) + 2 > limit and current:
                chunks.append(current.strip())
                current = ""
            current += block + "\n\n"
        if current.strip():
            chunks.append(current.strip())
        return chunks

    # ------------------------------------------------------------ analytics
    @learn.command(name="weak")
    async def learn_weak(self, ctx):
        """Topics where you've asked questions but written few notes."""
        rows = await asyncio.to_thread(self.engine.repo.weak_topics, 2, 10)
        if not rows:
            return await ctx.send(
                "Nothing flagged yet — that needs a few questions logged against "
                "the same topic."
            )

        lines = []
        for t in rows:
            bar = "█" * int(t["open_ratio"] * 10) + "░" * (10 - int(t["open_ratio"] * 10))
            lines.append(
                f"`{bar}` **{t['name']}**\n"
                f"　{t['questions']}❓ · {t['notes']}📝 · {t['revisions']}🔁"
            )

        embed = discord.Embed(
            title="⚠️ Unresolved topics",
            description="\n".join(lines),
            color=0xF0A836,
        )
        embed.set_footer(text="Full bar = asked about, never written up. Start here.")
        await ctx.send(embed=embed)

    @learn.command(name="stale")
    async def learn_stale(self, ctx, days: int = 14):
        """Topics you studied once and never came back to."""
        rows = await asyncio.to_thread(self.engine.repo.stale_topics, days, 10)
        if not rows:
            return await ctx.send(f"Nothing untouched for {days}+ days yet.")

        embed = discord.Embed(
            title=f"🕸️ Not revisited in {days}+ days",
            description="\n".join(
                f"**{t['name']}** — last seen `{t['last_seen']}` ({t['mentions']} mentions)"
                for t in rows),
            color=0x6FC3E8,
        )
        embed.set_footer(text="Never marked as revised. Prime candidates before an exam.")
        await ctx.send(embed=embed)

    @learn.command(name="topics")
    async def learn_topics(self, ctx, subject: str = None):
        """Every topic detected so far, ranked by how much you've covered it."""
        rows = await asyncio.to_thread(self.engine.repo.topic_stats, "topic", 100)
        if subject:
            rows = [r for r in rows if subject.lower() in (r["subject_key"] or "").lower()]
        if not rows:
            return await ctx.send("No topics detected yet.")

        groups: dict[str, list] = {}
        for r in rows[:40]:
            groups.setdefault(r["subject_key"] or "other", []).append(r)

        embed = discord.Embed(title="📚 Topics covered", color=0x46B39D)
        for subject_key, items in list(groups.items())[:6]:
            embed.add_field(
                name=subject_key.replace("_", " ").title(),
                value="\n".join(
                    f"`{i['mentions']:>2}×` {i['name']}"
                    + (f" ⚠️{i['questions']}❓" if i["open_ratio"] > 0.5 else "")
                    for i in items[:8]),
                inline=False)
        embed.set_footer(text="⚠️ = more questions than notes")
        await ctx.send(embed=embed)

    @learn.command(name="today")
    async def learn_today(self, ctx):
        """What you've logged today."""
        rows = await asyncio.to_thread(self.engine.repo.daily_activity, 1)
        if not rows or not rows[-1]["total"]:
            return await ctx.send("Nothing logged today yet.")

        day = rows[-1]
        breakdown = "\n".join(
            f"{LABEL_EMOJI.get(k, '·')} `{k:<9}` {v}"
            for k, v in day.items() if k not in ("date", "total"))

        embed = discord.Embed(
            title=f"📅 {day['date']}",
            description=f"**{day['total']}** messages captured\n\n{breakdown}",
            color=0x46B39D)
        embed.set_footer(text=f"{await asyncio.to_thread(self.engine.repo.streak)} day streak")
        await ctx.send(embed=embed)

    @learn.command(name="channels")
    async def learn_channels(self, ctx):
        """Show every mapped channel and how it was resolved."""
        mapped = self.engine.channels.all()
        if not mapped:
            return await ctx.send("No channels mapped. Run `!learn setup`.")

        groups: dict[str, list] = {}
        for c in sorted(mapped, key=lambda x: (x.context_value, x.label)):
            groups.setdefault(c.context_value or c.context_kind, []).append(c)

        embed = discord.Embed(title="📚 Mapped channels", color=0x5865F2)
        for group, channels in groups.items():
            embed.add_field(
                name=group,
                value="\n".join(
                    f"{'📕' if not c.captured else ('🔵' if c.origin == 'syllabus' else '⚪')} "
                    f"`{c.label}`" + (f" → `{c.subject_key}`" if c.subject_key else "")
                    for c in channels[:12]),
                inline=False)
        embed.set_footer(text="🔵 syllabus · ⚪ inferred · 📕 reference, not captured")
        await ctx.send(embed=embed)

    @learn.command(name="recent")
    async def learn_recent(self, ctx, count: int = 10):
        """Show the most recently captured messages with their labels."""
        rows = await asyncio.to_thread(
            self.engine.repo.entries, None, None, None, False, max(1, min(count, 15)), 0)
        if not rows:
            return await ctx.send("Nothing captured yet.")

        lines = []
        for r in rows:
            text = (r["content"] or "").replace("\n", " ")
            if len(text) > 60:
                text = text[:59] + "…"
            emoji = LABEL_EMOJI.get(r["label"], "·")
            flag = " ⚠️" if (r["confidence"] or 0) < 0.5 else ""
            lines.append(
                f"{emoji} `#{r['message_id']}` **{r['channel_label'] or '?'}**{flag}\n"
                f"　{text or '*(attachment)*'}")

        embed = discord.Embed(
            title="🕑 Recently captured",
            description="\n".join(lines),
            color=0x5865F2)
        embed.set_footer(text="⚠️ = low confidence · !learn fix <id> <label> to correct")
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
            if len(text) > 75:
                text = text[:74] + "…"
            lines.append(f"`{r['local_date']}` **{r['channel_label'] or '?'}** — {text}")

        await ctx.send(embed=discord.Embed(
            title=f"🔍 {len(rows)} result(s) for “{query}”",
            description="\n".join(lines), color=0x5865F2))

    @learn.command(name="fix")
    async def learn_fix(self, ctx, message_id: int, label: str):
        """Correct a wrong label. Your corrections become training data."""
        parsed = Label.parse(label)
        if parsed.value != label.strip().lower():
            return await ctx.send(
                f"Unknown label. Valid: {', '.join(f'`{l}`' for l in Label.values())}")

        ok = await asyncio.to_thread(self.engine.repo.relabel, message_id, parsed.value, "human")
        if not ok:
            return await ctx.send(f"No message `#{message_id}` found.")
        await ctx.send(
            f"{LABEL_EMOJI.get(parsed.value)} `#{message_id}` is now **{parsed.value}**. "
            f"Stored as a correction.")


async def setup(bot):
    await bot.add_cog(LearningCommands(bot))
