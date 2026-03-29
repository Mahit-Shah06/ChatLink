import discord
from discord.ext import commands

class Retard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command()
    async def retard(self, ctx, member: discord.Member):
        await ctx.send(f"**{member.mention}** you are a retard.")

async def setup(bot):
    await bot.add_cog(Retard(bot))
