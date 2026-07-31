import logging

import discord
from discord.ext import commands

from bot.services.secret_santa_service import SecretSantaService

log = logging.getLogger("chatlink.secretsanta")


class SecretSanta(commands.Cog):
    """Secret Santa draw.

    Previously these were bare @bot.command() registrations inside setup(), so
    they belonged to no cog and help filed them under "Other". As a proper Cog
    they group correctly, and each command now carries a docstring for help to
    read. Names and behaviour are unchanged: !ssadd, !ssmems, !ssbegin,
    !ssremoveall.

    Note: SecretSantaService keeps one participant list for the whole bot, not
    one per guild. Across two servers, that list is shared.
    """

    def __init__(self, bot):
        self.bot = bot
        self.ss = SecretSantaService()

    @commands.command(name="ssadd")
    async def ssadd(self, ctx, member: discord.Member = None):
        """Join the Secret Santa draw, or add someone else."""
        member = member or ctx.author
        if self.ss.add_member(member):
            await ctx.reply(f"✅ {member.mention} added.")
        else:
            await ctx.reply(f"⚠️ {member.mention} is already in.")

    @commands.command(name="ssmems")
    async def ssmems(self, ctx):
        """List everyone entered in the draw."""
        entries = self.ss.get_entries()
        if not entries:
            return await ctx.reply("🎄 No participants yet. Run `!ssadd` to join.")

        embed = discord.Embed(
            title="🎁 Secret Santa",
            description="\n".join(f"• {name}" for _, name in entries),
            color=0xE23B3B,
        )
        embed.set_footer(text=f"{len(entries)} participant(s)")
        await ctx.reply(embed=embed)

    @commands.command(name="ssbegin")
    @commands.has_permissions(administrator=True)
    async def ssbegin(self, ctx):
        """Draw names and DM everyone their match. Admin only."""
        result = self.ss.generate_pairs()
        if not result:
            return await ctx.reply("❌ Need at least 2 participants.")

        ids, shuffled, names = result
        failed = []

        for giver, receiver in zip(ids, shuffled):
            try:
                user = await ctx.bot.fetch_user(giver)
                await user.send(f"🎅 You are Secret Santa for **{names[receiver]}** 🤫")
            except discord.Forbidden:
                failed.append(names[giver])
            except Exception as exc:
                log.error("failed to DM %s: %s", giver, exc)
                failed.append(names[giver])

        if failed:
            await ctx.reply(f"⚠️ Could not DM: {', '.join(failed)}")
        else:
            await ctx.reply("🎄 Secret Santa started! Check your DMs.")

    @commands.command(name="ssremoveall")
    @commands.has_permissions(administrator=True)
    async def ssremoveall(self, ctx):
        """Clear every participant and reset the draw. Admin only."""
        self.ss.clear()
        await ctx.reply("🗑️ All participants removed.")


async def setup(bot):
    await bot.add_cog(SecretSanta(bot))
