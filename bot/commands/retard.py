import discord
from discord.ext import commands

class API(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def retard(self, ctx, member: discord.Member):
        await ctx.send(f"**{member.display_name}** you are a retard.")

async def setup(bot):
    await bot.add_cog(API(bot))
