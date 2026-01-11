import discord
from discord.ext import commands

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- PURGE ----------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def purge(self, ctx, count: int = 1):
        """
        Delete last N messages (max 50)
        """
        count = min(count, 50)
        await ctx.channel.purge(limit=count + 1)

    # ---------- LOCK CHANNEL ----------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def lock(self, ctx):
        """
        Lock current channel (no one can send messages)
        """
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply("🔒 Channel locked.")

    # ---------- UNLOCK CHANNEL ----------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def unlock(self, ctx):
        """
        Unlock current channel
        """
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply("🔓 Channel unlocked.")

    # ---------- ANNOUNCE ----------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx, *, message: str):
        """
        Send announcement embed
        """
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=0xffcc00
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
