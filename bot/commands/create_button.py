import discord
from discord.ext import commands
from ui.create_button_ui import CreateView

class CreateButton(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def cb(self, ctx):
        embed = discord.Embed(
            title="Start Chat",
            description="Click the button below to create a private ChatGPT session",
            color=0x00ff99
        )
        await ctx.send(embed=embed, view=CreateView())

async def setup(bot):
    await bot.add_cog(CreateButton(bot))
