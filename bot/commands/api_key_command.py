import discord
from discord.ext import commands
from ui.api_key_ui import APIKeyView

class API(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def capi(self, ctx):
        await ctx.send("Add API keys:", view=APIKeyView())

async def setup(bot):
    await bot.add_cog(API(bot))
