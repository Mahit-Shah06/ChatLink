import discord
from discord.ext import commands
from bot.services.secret_santa_service import SecretSantaService

ss = SecretSantaService()

def setup(bot):

    @bot.command()
    async def ssadd(ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author

        if ss.add_member(member):
            await ctx.reply(f"✅ {member.mention} added.")
        else:
            await ctx.reply(f"⚠️ {member.mention} already added.")

    @bot.command()
    async def ssmems(ctx):
        entries = ss.get_entries()
        if not entries:
            return await ctx.reply("🎄 No participants yet.")

        msg = "\n".join(f"• {name}" for _, name in entries)
        await ctx.reply(f"🎁 Participants:\n{msg}")

    @bot.command()
    @commands.has_permissions(administrator=True)
    async def ssbegin(ctx):
        result = ss.generate_pairs()
        if not result:
            return await ctx.reply("❌ Need at least 2 participants.")

        ids, shuffled, names = result
        failed = []

        for giver, receiver in zip(ids, shuffled):
            try:
                user = await ctx.bot.fetch_user(giver)
                await user.send(
                    f"🎅 You are Secret Santa for **{names[receiver]}** 🤫"
                )
            except Exception:
                failed.append(names[giver])

        if failed:
            await ctx.reply(f"⚠️ Could not DM: {', '.join(failed)}")
        else:
            await ctx.reply("🎄 Secret Santa started!")

    @bot.command()
    @commands.has_permissions(administrator=True)
    async def ssremoveall(ctx):
        ss.clear()
        await ctx.reply("🗑️ All participants removed.")
