import logging

import discord
from discord.ext import commands

log = logging.getLogger("chatlink.admin")


class AdminCommands(commands.Cog):
    """Moderation and server utilities.

    The logging commands (!setup_logs, !toggle_logs, !logs) moved to
    bot/commands/logging_commands.py. Same command names, different cog, so
    help can group them sensibly instead of listing everything as "Admin".

    Every command now has a docstring, because help is generated from them.
    """

    def __init__(self, bot):
        self.bot = bot

    # ------------------------------------------------------------ moderation
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def purge(self, ctx, count: int = 1):
        """Delete the last N messages in this channel, up to 50."""
        count = max(1, min(count, 50))
        deleted = await ctx.channel.purge(limit=count + 1)
        # +1 accounts for the command message itself
        await ctx.send(f"🧹 Deleted {len(deleted) - 1} message(s).", delete_after=5)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def lock(self, ctx):
        """Stop everyone from sending messages in this channel."""
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply("🔒 Channel locked.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def unlock(self, ctx):
        """Let everyone send messages in this channel again."""
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply("🔓 Channel unlocked.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx, *, message: str):
        """Post a message as a highlighted announcement embed."""
        embed = discord.Embed(title="📢 Announcement", description=message, color=0xFFCC00)
        embed.set_footer(text=f"Posted by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    # ----------------------------------------------------------------- roles
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def create_role(self, ctx, *, role_name: str):
        """Create a new role with no permissions."""
        existing = discord.utils.get(ctx.guild.roles, name=role_name)
        if existing:
            return await ctx.send(f"⚠️ **{role_name}** already exists (`{existing.id}`).")
        try:
            role = await ctx.guild.create_role(name=role_name)
        except discord.Forbidden:
            return await ctx.send("❌ I don't have permission to create roles.")
        await ctx.send(f"✅ Created **{role.name}** — `{role.id}`")

    # --------------------------------------------------------------- utility
    @commands.hybrid_command(name="servericon")
    async def servericon(self, ctx):
        """Show this server's icon at full size."""
        if not ctx.guild.icon:
            return await ctx.send("❌ This server has no icon set.")
        embed = discord.Embed(
            title=f"{ctx.guild.name}", color=discord.Color.blurple()
        )
        embed.set_image(url=ctx.guild.icon.with_size(4096).url)
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pfp")
    async def pfp(self, ctx, user: discord.Member = None):
        """Show someone's profile picture at full size."""
        user = user or ctx.author
        embed = discord.Embed(
            title=f"{user.display_name}", color=discord.Color.blurple()
        )
        embed.set_image(url=user.display_avatar.with_size(4096).url)
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
