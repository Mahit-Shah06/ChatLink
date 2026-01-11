import discord
from discord.ext import commands
from bot.ui.api_key_ui import APIKeyView

class API(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def capi(self, ctx):
        await ctx.channel.purge(limit=1)
        embed = discord.Embed(
            title="Add API keys",
            description="Click the button below to add your api key",
            color=0x00ff88
        )
        await ctx.send(embed=embed, view=APIKeyView())

async def setup(bot):
    await bot.add_cog(API(bot))
