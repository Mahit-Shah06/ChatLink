import discord
from discord.ext import commands
from bot.ui.api_key_ui import APIKeyView


class APIKeyCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="capi")
    async def capi(self, ctx: commands.Context):
        await ctx.send(
            "Click the button below to securely add your API key:",
            view=APIKeyView()
        )


async def setup(bot):
    await bot.add_cog(APIKeyCommand(bot))
